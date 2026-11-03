package sources

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

type Jamendo struct {
	baseURL  *url.URL
	client   *http.Client
	clientID string
	limit    int
}

type jamendoResponse struct {
	Headers struct {
		Status       string `json:"status"`
		Code         int    `json:"code"`
		ErrorMessage string `json:"error_message"`
	} `json:"headers"`
	Results []jamendoTrack `json:"results"`
}

type jamendoTrack struct {
	Name                 string `json:"name"`
	Duration             int    `json:"duration"`
	ArtistName           string `json:"artist_name"`
	Image                string `json:"image"`
	ShareURL             string `json:"shareurl"`
	AudioDownload        string `json:"audiodownload"`
	AudioDownloadAllowed bool   `json:"audiodownload_allowed"`
}

func NewJamendo(client *http.Client, rawBaseURL, clientID string, limit int) (*Jamendo, error) {
	baseURL, err := url.Parse(rawBaseURL)
	if err != nil || baseURL.Scheme == "" || baseURL.Host == "" {
		return nil, errors.New("invalid Jamendo base URL")
	}
	if strings.TrimSpace(clientID) == "" {
		return nil, errors.New("Jamendo client ID is required")
	}
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second}
	}
	if limit <= 0 {
		limit = 10
	}
	return &Jamendo{baseURL: baseURL, client: client, clientID: clientID, limit: limit}, nil
}

func (jamendo *Jamendo) Search(ctx context.Context, query string) ([]Result, error) {
	searchURL := jamendo.baseURL.ResolveReference(&url.URL{Path: "/v3.0/tracks/"})
	parameters := searchURL.Query()
	parameters.Set("client_id", jamendo.clientID)
	parameters.Set("format", "json")
	parameters.Set("limit", strconv.Itoa(jamendo.limit))
	parameters.Set("search", query)
	parameters.Set("imagesize", "300")
	parameters.Set("audiodlformat", "mp32")
	parameters.Set("type", "single albumtrack")
	searchURL.RawQuery = parameters.Encode()

	body, err := getJSON(ctx, jamendo.client, searchURL.String(), "Jamendo")
	if err != nil {
		return nil, err
	}

	var payload jamendoResponse
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil, fmt.Errorf("%w: invalid Jamendo JSON", ErrUnexpectedResponse)
	}
	if payload.Headers.Status != "success" || payload.Headers.Code != 0 {
		return nil, fmt.Errorf("Jamendo API error %d: %s", payload.Headers.Code, payload.Headers.ErrorMessage)
	}
	results := make([]Result, 0, len(payload.Results))
	for _, track := range payload.Results {
		if strings.TrimSpace(track.Name) == "" || strings.TrimSpace(track.ArtistName) == "" || strings.TrimSpace(track.ShareURL) == "" {
			return nil, fmt.Errorf("%w: incomplete Jamendo result", ErrUnexpectedResponse)
		}
		result := Result{
			Title:          track.Name,
			Artist:         track.ArtistName,
			Duration:       formatSeconds(track.Duration),
			Cover:          track.Image,
			Source:         "jamendo",
			PageURL:        track.ShareURL,
			DownloadMethod: DownloadNone,
		}
		if track.AudioDownloadAllowed && track.AudioDownload != "" {
			result.Format = "mp3"
			result.Quality = "VBR (mp32)"
			result.DownloadAvailable = true
			result.DownloadMethod = DownloadDirect
			result.DownloadURL = track.AudioDownload
		}
		results = append(results, result)
	}
	return results, nil
}

func formatSeconds(seconds int) string {
	if seconds <= 0 {
		return ""
	}
	return fmt.Sprintf("%d:%02d", seconds/60, seconds%60)
}
