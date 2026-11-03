package sources

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
)

const (
	maxResponseSize = 2 << 20

	DownloadDirect   = "direct"
	DownloadExternal = "external"
	DownloadNone     = "none"
)

var ErrUnexpectedResponse = errors.New("unexpected source response")

type Variant struct {
	Source            string `json:"source"`
	Duration          string `json:"duration,omitempty"`
	Cover             string `json:"cover,omitempty"`
	PageURL           string `json:"pageUrl"`
	Format            string `json:"format,omitempty"`
	Quality           string `json:"quality,omitempty"`
	DownloadAvailable bool   `json:"downloadAvailable"`
	DownloadMethod    string `json:"downloadMethod"`
	DownloadURL       string `json:"downloadUrl,omitempty"`
}

type Result struct {
	Title             string    `json:"title"`
	Artist            string    `json:"artist"`
	Duration          string    `json:"duration"`
	Cover             string    `json:"cover"`
	Source            string    `json:"source"`
	PageURL           string    `json:"pageUrl"`
	Format            string    `json:"format,omitempty"`
	Quality           string    `json:"quality,omitempty"`
	DownloadAvailable bool      `json:"downloadAvailable"`
	DownloadMethod    string    `json:"downloadMethod"`
	DownloadURL       string    `json:"downloadUrl,omitempty"`
	InLibrary         bool      `json:"inLibrary"`
	LibraryTrackID    int       `json:"libraryTrackId,omitempty"`
	Variants          []Variant `json:"variants"`
}

func (result Result) Variant() Variant {
	return Variant{
		Source:            result.Source,
		Duration:          result.Duration,
		Cover:             result.Cover,
		PageURL:           result.PageURL,
		Format:            result.Format,
		Quality:           result.Quality,
		DownloadAvailable: result.DownloadAvailable,
		DownloadMethod:    result.DownloadMethod,
		DownloadURL:       result.DownloadURL,
	}
}

type Searcher interface {
	Search(context.Context, string) ([]Result, error)
}

type Provider struct {
	Searcher          Searcher
	ExternalSearchURL string
	QueryParameter    string
	UnavailableReason string
}

func getJSON(ctx context.Context, client *http.Client, target, sourceName string) ([]byte, error) {
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, target, nil)
	if err != nil {
		return nil, err
	}
	request.Header.Set("Accept", "application/json")
	request.Header.Set("User-Agent", "WaveBox/1.0")
	response, err := client.Do(request)
	if err != nil {
		return nil, fmt.Errorf("request %s: %w", sourceName, err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("%s returned status %d", sourceName, response.StatusCode)
	}
	body, err := io.ReadAll(io.LimitReader(response.Body, maxResponseSize+1))
	if err != nil {
		return nil, fmt.Errorf("read %s response: %w", sourceName, err)
	}
	if len(body) > maxResponseSize {
		return nil, fmt.Errorf("%w: response is too large", ErrUnexpectedResponse)
	}
	return body, nil
}
