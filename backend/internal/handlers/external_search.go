package handlers

import (
	"context"
	"database/sql"
	"encoding/json"
	"log"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"
	"unicode"

	"wavebox/backend/internal/models"
	"wavebox/backend/internal/sources"
	"wavebox/backend/internal/store"
)

const (
	defaultExternalLimit = 20
	maximumExternalLimit = 50
)

type externalSearchResponse struct {
	Source        string           `json:"source,omitempty"`
	Sources       []string         `json:"sources"`
	Results       []sources.Result `json:"results"`
	Errors        []sourceError    `json:"errors,omitempty"`
	ExternalLinks []externalLink   `json:"externalLinks,omitempty"`
}

type sourceError struct {
	Source  string `json:"source"`
	Message string `json:"message"`
}

type externalLink struct {
	Source string `json:"source"`
	URL    string `json:"url"`
	Reason string `json:"reason"`
}

type searchOutcome struct {
	source  string
	results []sources.Result
	err     error
}

func SearchExternal(db *sql.DB, providers map[string]sources.Provider, sourceTimeout time.Duration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		query := strings.TrimSpace(r.URL.Query().Get("q"))
		selected := parseSources(r.URL.Query())
		limit, err := parseLimit(r.URL.Query().Get("limit"))
		if query == "" || len(query) > 200 || len(selected) == 0 || err != nil {
			http.Error(w, "valid source, q, and limit are required", http.StatusBadRequest)
			return
		}
		for _, name := range selected {
			if _, ok := providers[name]; !ok {
				http.Error(w, "unknown source", http.StatusBadRequest)
				return
			}
		}

		searchers := make(map[string]sources.Searcher)
		links := make([]externalLink, 0)
		for _, name := range selected {
			provider := providers[name]
			if provider.Searcher != nil {
				searchers[name] = provider.Searcher
				continue
			}
			links = append(links, externalLink{
				Source: name,
				URL:    externalSearchURL(provider, query),
				Reason: provider.UnavailableReason,
			})
		}

		outcomes := searchSources(r.Context(), selected, searchers, query, sourceTimeout)
		errorsBySource := make(map[string]error)
		successfulOutcomes := make([]searchOutcome, 0, len(outcomes))
		successful := 0
		for _, outcome := range outcomes {
			if outcome.err != nil {
				errorsBySource[outcome.source] = outcome.err
				log.Printf("search external source %s: %v", outcome.source, outcome.err)
				continue
			}
			successful++
			for index, result := range outcome.results {
				result.Source = outcome.source
				if result.DownloadMethod == "" {
					result.DownloadMethod = sources.DownloadNone
				}
				outcome.results[index] = result
			}
			successfulOutcomes = append(successfulOutcomes, outcome)
		}
		if len(searchers) > 0 && successful == 0 && len(links) == 0 {
			http.Error(w, "external source is unavailable", http.StatusBadGateway)
			return
		}

		results := deduplicateResults(interleaveResults(successfulOutcomes))
		if len(results) > limit {
			results = results[:limit]
		}
		if len(results) > 0 {
			library, err := store.GetTracks(r.Context(), db)
			if err != nil {
				log.Printf("load library for external search: %v", err)
				http.Error(w, "failed to check music library", http.StatusInternalServerError)
				return
			}
			markLibrary(results, library)
		}

		response := externalSearchResponse{
			Sources:       selected,
			Results:       results,
			ExternalLinks: links,
		}
		if len(selected) == 1 {
			response.Source = selected[0]
		}
		for _, name := range selected {
			if _, ok := errorsBySource[name]; ok {
				response.Errors = append(response.Errors, sourceError{Source: name, Message: "source unavailable"})
			}
		}

		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(response); err != nil {
			log.Printf("encode external search: %v", err)
		}
	}
}

func interleaveResults(outcomes []searchOutcome) []sources.Result {
	combined := make([]sources.Result, 0)
	for index := 0; ; index++ {
		added := false
		for _, outcome := range outcomes {
			if index < len(outcome.results) {
				combined = append(combined, outcome.results[index])
				added = true
			}
		}
		if !added {
			return combined
		}
	}
}

func parseSources(values url.Values) []string {
	seen := make(map[string]bool)
	selected := make([]string, 0)
	for _, key := range []string{"source", "sources"} {
		for _, value := range values[key] {
			for _, name := range strings.Split(value, ",") {
				name = strings.TrimSpace(name)
				if name != "" && !seen[name] {
					seen[name] = true
					selected = append(selected, name)
				}
			}
		}
	}
	return selected
}

func parseLimit(raw string) (int, error) {
	if raw == "" {
		return defaultExternalLimit, nil
	}
	limit, err := strconv.Atoi(raw)
	if err != nil || limit <= 0 || limit > maximumExternalLimit {
		return 0, strconv.ErrSyntax
	}
	return limit, nil
}

func externalSearchURL(provider sources.Provider, query string) string {
	parsed, err := url.Parse(provider.ExternalSearchURL)
	if err != nil || provider.QueryParameter == "" {
		return provider.ExternalSearchURL
	}
	parameters := parsed.Query()
	parameters.Set(provider.QueryParameter, query)
	parsed.RawQuery = parameters.Encode()
	return parsed.String()
}

func searchSources(ctx context.Context, selected []string, searchers map[string]sources.Searcher, query string, timeout time.Duration) []searchOutcome {
	channel := make(chan searchOutcome, len(searchers))
	var waitGroup sync.WaitGroup
	for _, name := range selected {
		searcher, ok := searchers[name]
		if !ok {
			continue
		}
		waitGroup.Add(1)
		go func(source string, searcher sources.Searcher) {
			defer waitGroup.Done()
			sourceContext, cancel := context.WithTimeout(ctx, timeout)
			defer cancel()
			results, err := searcher.Search(sourceContext, query)
			channel <- searchOutcome{source: source, results: results, err: err}
		}(name, searcher)
	}
	waitGroup.Wait()
	close(channel)

	bySource := make(map[string]searchOutcome, len(searchers))
	for outcome := range channel {
		bySource[outcome.source] = outcome
	}
	outcomes := make([]searchOutcome, 0, len(searchers))
	for _, name := range selected {
		if outcome, ok := bySource[name]; ok {
			outcomes = append(outcomes, outcome)
		}
	}
	return outcomes
}

func deduplicateResults(results []sources.Result) []sources.Result {
	groups := make([]sources.Result, 0, len(results))
	for _, result := range results {
		match := -1
		for index := range groups {
			if sameRecording(groups[index], result) {
				match = index
				break
			}
		}
		if match == -1 {
			result.Variants = []sources.Variant{result.Variant()}
			groups = append(groups, result)
			continue
		}

		variants := append(groups[match].Variants, result.Variant())
		if downloadRank(result.DownloadMethod) > downloadRank(groups[match].DownloadMethod) {
			result.Variants = variants
			groups[match] = result
		} else {
			groups[match].Variants = variants
		}
	}
	return groups
}

func sameRecording(left, right sources.Result) bool {
	if left.Source == right.Source || left.Artist == "" || right.Artist == "" {
		return false
	}
	if normalizeIdentity(left.Title) != normalizeIdentity(right.Title) || normalizeIdentity(left.Artist) != normalizeIdentity(right.Artist) {
		return false
	}
	leftDuration, leftOK := durationSeconds(left.Duration)
	rightDuration, rightOK := durationSeconds(right.Duration)
	if !leftOK || !rightOK {
		return false
	}
	return absolute(leftDuration-rightDuration) <= 3
}

func downloadRank(method string) int {
	switch method {
	case sources.DownloadDirect:
		return 2
	case sources.DownloadExternal:
		return 1
	default:
		return 0
	}
}

func markLibrary(results []sources.Result, library []models.Track) {
	for index := range results {
		for _, track := range library {
			if normalizeIdentity(results[index].Title) != normalizeIdentity(track.Title) || normalizeIdentity(results[index].Artist) != normalizeIdentity(track.Artist) {
				continue
			}
			externalDuration, externalOK := durationSeconds(results[index].Duration)
			localDuration, localOK := durationSeconds(track.Duration)
			if externalOK && localOK && absolute(externalDuration-localDuration) > 3 {
				continue
			}
			results[index].InLibrary = true
			results[index].LibraryTrackID = track.ID
			break
		}
	}
}

func normalizeIdentity(value string) string {
	var normalized strings.Builder
	for _, character := range strings.ToLower(strings.TrimSpace(value)) {
		if unicode.IsLetter(character) || unicode.IsDigit(character) {
			normalized.WriteRune(character)
		}
	}
	return normalized.String()
}

func durationSeconds(value string) (int, bool) {
	parts := strings.Split(value, ":")
	if len(parts) != 2 {
		return 0, false
	}
	minutes, minutesError := strconv.Atoi(parts[0])
	seconds, secondsError := strconv.Atoi(parts[1])
	if minutesError != nil || secondsError != nil || minutes < 0 || seconds < 0 || seconds >= 60 {
		return 0, false
	}
	return minutes*60 + seconds, true
}

func absolute(value int) int {
	if value < 0 {
		return -value
	}
	return value
}
