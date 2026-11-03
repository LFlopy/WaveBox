package sources

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

const maxResponseSize = 2 << 20

var (
	ErrUnexpectedResponse = errors.New("unexpected source response")
	jsonLDScriptPattern   = regexp.MustCompile(`(?is)<script\b[^>]*\btype\s*=\s*["']application/ld\+json["'][^>]*>(.*?)</script>`)
	durationPattern       = regexp.MustCompile(`^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$`)
)

type Result struct {
	Title    string `json:"title"`
	Artist   string `json:"artist"`
	Duration string `json:"duration"`
	Cover    string `json:"cover"`
	PageURL  string `json:"pageUrl"`
}

type Searcher interface {
	Search(context.Context, string) ([]Result, error)
}

type Muzsky struct {
	baseURL     *url.URL
	client      *http.Client
	interval    time.Duration
	requestMu   sync.Mutex
	nextRequest time.Time
}

type muzskySuggestion struct {
	Type  string `json:"type"`
	Title string `json:"title"`
	Sub   string `json:"sub"`
	URL   string `json:"url"`
	Image string `json:"img"`
}

func NewMuzsky(client *http.Client, rawBaseURL string, interval time.Duration) (*Muzsky, error) {
	baseURL, err := url.Parse(rawBaseURL)
	if err != nil || baseURL.Scheme == "" || baseURL.Host == "" {
		return nil, errors.New("invalid Muzsky base URL")
	}

	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second}
	}
	clientCopy := *client
	originalRedirect := clientCopy.CheckRedirect
	clientCopy.CheckRedirect = func(req *http.Request, via []*http.Request) error {
		if !allowedURL(baseURL, req.URL) {
			return errors.New("source redirected outside allowed host")
		}
		if originalRedirect != nil {
			return originalRedirect(req, via)
		}
		if len(via) >= 10 {
			return errors.New("too many source redirects")
		}
		return nil
	}

	return &Muzsky{
		baseURL:  baseURL,
		client:   &clientCopy,
		interval: interval,
	}, nil
}

func (m *Muzsky) Search(ctx context.Context, query string) ([]Result, error) {
	ctx, cancel := context.WithTimeout(ctx, 20*time.Second)
	defer cancel()

	searchURL := m.baseURL.ResolveReference(&url.URL{Path: "/suggest.php"})
	parameters := searchURL.Query()
	parameters.Set("q", query)
	searchURL.RawQuery = parameters.Encode()

	body, err := m.get(ctx, searchURL)
	if err != nil {
		return nil, err
	}

	var suggestions []muzskySuggestion
	if err := json.Unmarshal(body, &suggestions); err != nil {
		return nil, fmt.Errorf("%w: invalid search JSON", ErrUnexpectedResponse)
	}

	results := make([]Result, 0, len(suggestions))
	for _, suggestion := range suggestions {
		if suggestion.Type != "track" {
			continue
		}
		if strings.TrimSpace(suggestion.Title) == "" || strings.TrimSpace(suggestion.Sub) == "" || strings.TrimSpace(suggestion.URL) == "" {
			return nil, fmt.Errorf("%w: incomplete track result", ErrUnexpectedResponse)
		}

		pageURL, err := m.resolveAllowedURL(suggestion.URL)
		if err != nil {
			return nil, fmt.Errorf("%w: invalid track URL", ErrUnexpectedResponse)
		}
		page, err := m.get(ctx, pageURL)
		if err != nil {
			return nil, err
		}
		duration, err := parseDuration(page)
		if err != nil {
			return nil, err
		}

		cover := ""
		if suggestion.Image != "" {
			coverURL, err := m.resolveAllowedURL(suggestion.Image)
			if err != nil {
				return nil, fmt.Errorf("%w: invalid cover URL", ErrUnexpectedResponse)
			}
			cover = coverURL.String()
		}

		results = append(results, Result{
			Title:    suggestion.Title,
			Artist:   suggestion.Sub,
			Duration: duration,
			Cover:    cover,
			PageURL:  pageURL.String(),
		})
	}

	return results, nil
}

func (m *Muzsky) get(ctx context.Context, target *url.URL) ([]byte, error) {
	if !allowedURL(m.baseURL, target) {
		return nil, errors.New("source URL is not allowed")
	}
	if err := m.wait(ctx); err != nil {
		return nil, err
	}

	request, err := http.NewRequestWithContext(ctx, http.MethodGet, target.String(), nil)
	if err != nil {
		return nil, err
	}
	request.Header.Set("Accept", "application/json, text/html;q=0.9")
	request.Header.Set("User-Agent", "WaveBox/1.0")

	response, err := m.client.Do(request)
	if err != nil {
		return nil, fmt.Errorf("request source: %w", err)
	}
	defer response.Body.Close()

	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("source returned status %d", response.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(response.Body, maxResponseSize+1))
	if err != nil {
		return nil, fmt.Errorf("read source response: %w", err)
	}
	if len(body) > maxResponseSize {
		return nil, fmt.Errorf("%w: response is too large", ErrUnexpectedResponse)
	}
	return body, nil
}

func (m *Muzsky) wait(ctx context.Context) error {
	m.requestMu.Lock()
	now := time.Now()
	requestAt := now
	if m.nextRequest.After(now) {
		requestAt = m.nextRequest
	}
	m.nextRequest = requestAt.Add(m.interval)
	m.requestMu.Unlock()

	delay := time.Until(requestAt)
	if delay <= 0 {
		return nil
	}
	timer := time.NewTimer(delay)
	defer timer.Stop()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-timer.C:
		return nil
	}
}

func (m *Muzsky) resolveAllowedURL(reference string) (*url.URL, error) {
	parsed, err := url.Parse(reference)
	if err != nil {
		return nil, err
	}
	resolved := m.baseURL.ResolveReference(parsed)
	if !allowedURL(m.baseURL, resolved) {
		return nil, errors.New("URL is outside source host")
	}
	return resolved, nil
}

func allowedURL(baseURL, target *url.URL) bool {
	if target.Scheme != baseURL.Scheme || target.Port() != baseURL.Port() {
		return false
	}
	baseHost := strings.ToLower(baseURL.Hostname())
	targetHost := strings.ToLower(target.Hostname())
	return targetHost == baseHost || strings.HasSuffix(targetHost, "."+baseHost)
}

func parseDuration(page []byte) (string, error) {
	for _, match := range jsonLDScriptPattern.FindAllSubmatch(page, -1) {
		var value any
		if err := json.Unmarshal(match[1], &value); err != nil {
			continue
		}
		if duration := findRecordingDuration(value); duration != "" {
			return formatDuration(duration)
		}
	}
	return "", fmt.Errorf("%w: track duration is missing", ErrUnexpectedResponse)
}

func findRecordingDuration(value any) string {
	switch typed := value.(type) {
	case []any:
		for _, item := range typed {
			if duration := findRecordingDuration(item); duration != "" {
				return duration
			}
		}
	case map[string]any:
		if typed["@type"] == "MusicRecording" {
			duration, _ := typed["duration"].(string)
			return duration
		}
		for _, item := range typed {
			if duration := findRecordingDuration(item); duration != "" {
				return duration
			}
		}
	}
	return ""
}

func formatDuration(value string) (string, error) {
	parts := durationPattern.FindStringSubmatch(value)
	if parts == nil {
		return "", fmt.Errorf("%w: invalid track duration", ErrUnexpectedResponse)
	}
	hours, _ := strconv.Atoi(parts[1])
	minutes, _ := strconv.Atoi(parts[2])
	seconds, _ := strconv.Atoi(parts[3])
	return fmt.Sprintf("%d:%02d", hours*60+minutes, seconds), nil
}
