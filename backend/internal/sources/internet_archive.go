package sources

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strings"
	"time"
)

type InternetArchive struct {
	baseURL *url.URL
	client  *http.Client
	limit   int
}

type archiveSearchResponse struct {
	Response struct {
		Docs []archiveDocument `json:"docs"`
	} `json:"response"`
}

type archiveDocument struct {
	Identifier string          `json:"identifier"`
	Title      string          `json:"title"`
	Creator    archiveCreators `json:"creator"`
	Formats    []string        `json:"format"`
}

type archiveCreators []string

func (creators *archiveCreators) UnmarshalJSON(data []byte) error {
	if string(data) == "null" {
		*creators = nil
		return nil
	}
	var single string
	if err := json.Unmarshal(data, &single); err == nil {
		*creators = []string{single}
		return nil
	}
	var multiple []string
	if err := json.Unmarshal(data, &multiple); err != nil {
		return err
	}
	*creators = multiple
	return nil
}

func NewInternetArchive(client *http.Client, rawBaseURL string, limit int) (*InternetArchive, error) {
	baseURL, err := url.Parse(rawBaseURL)
	if err != nil || baseURL.Scheme == "" || baseURL.Host == "" {
		return nil, errors.New("invalid Internet Archive base URL")
	}
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second}
	}
	if limit <= 0 {
		limit = 10
	}
	return &InternetArchive{baseURL: baseURL, client: client, limit: limit}, nil
}

func (archive *InternetArchive) Search(ctx context.Context, query string) ([]Result, error) {
	searchURL := archive.baseURL.ResolveReference(&url.URL{Path: "/advancedsearch.php"})
	parameters := searchURL.Query()
	parameters.Set("q", archiveQuery(query))
	for _, field := range []string{"identifier", "title", "creator", "format"} {
		parameters.Add("fl[]", field)
	}
	parameters.Set("rows", fmt.Sprintf("%d", archive.limit))
	parameters.Set("page", "1")
	parameters.Set("output", "json")
	searchURL.RawQuery = parameters.Encode()

	body, err := getJSON(ctx, archive.client, searchURL.String(), "Internet Archive")
	if err != nil {
		return nil, err
	}

	var payload archiveSearchResponse
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil, fmt.Errorf("%w: invalid Internet Archive JSON", ErrUnexpectedResponse)
	}
	results := make([]Result, 0, len(payload.Response.Docs))
	for _, document := range payload.Response.Docs {
		if strings.TrimSpace(document.Identifier) == "" || strings.TrimSpace(document.Title) == "" {
			return nil, fmt.Errorf("%w: incomplete Internet Archive result", ErrUnexpectedResponse)
		}
		format, quality := archiveFormat(document.Formats)
		results = append(results, Result{
			Title:          document.Title,
			Artist:         strings.Join(document.Creator, "; "),
			Cover:          archive.baseURL.ResolveReference(&url.URL{Path: "/services/img/" + document.Identifier}).String(),
			Source:         "internet_archive",
			PageURL:        archive.baseURL.ResolveReference(&url.URL{Path: "/details/" + document.Identifier}).String(),
			Format:         format,
			Quality:        quality,
			DownloadMethod: DownloadExternal,
		})
	}
	return results, nil
}

func archiveQuery(query string) string {
	escaped := strings.NewReplacer(`\`, `\\`, `"`, `\"`).Replace(strings.TrimSpace(query))
	return fmt.Sprintf(`mediatype:audio AND (title:"%s" OR creator:"%s")`, escaped, escaped)
}

func archiveFormat(formats []string) (string, string) {
	found := make(map[string]string)
	for _, value := range formats {
		lower := strings.ToLower(value)
		switch {
		case strings.Contains(lower, "flac"):
			found["flac"] = value
		case strings.Contains(lower, "mp3") && !strings.Contains(lower, "m3u"):
			found["mp3"] = value
		case strings.Contains(lower, "ogg"):
			found["ogg"] = value
		case strings.Contains(lower, "mpeg-4 audio"):
			found["m4a"] = value
		}
	}
	if len(found) != 1 {
		return "", ""
	}
	for format, quality := range found {
		return format, quality
	}
	return "", ""
}
