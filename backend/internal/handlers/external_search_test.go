package handlers

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/DATA-DOG/go-sqlmock"
	"wavebox/backend/internal/models"
	"wavebox/backend/internal/sources"
)

type fakeExternalSearcher struct {
	search func(context.Context, string) ([]sources.Result, error)
}

func (fake fakeExternalSearcher) Search(ctx context.Context, query string) ([]sources.Result, error) {
	return fake.search(ctx, query)
}

func resultsSearcher(results []sources.Result) sources.Searcher {
	return fakeExternalSearcher{search: func(context.Context, string) ([]sources.Result, error) {
		return results, nil
	}}
}

func TestSearchExternalBackwardCompatibilityAndLibraryMatch(t *testing.T) {
	db, mock := libraryDatabase(t, models.Track{ID: 7, Title: "show", Artist: "ADO", Duration: "3:11"})
	defer db.Close()
	providers := map[string]sources.Provider{
		"muzsky": {Searcher: resultsSearcher([]sources.Result{{
			Title: "Show", Artist: "Ado", Duration: "3:10", PageURL: "https://ado.muzsky.net/music/ado-show",
			DownloadMethod: sources.DownloadExternal,
		}})},
	}
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/api/external/search?source=muzsky&q=Ado", nil)

	SearchExternal(db, providers, time.Second)(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d: %s", recorder.Code, recorder.Body.String())
	}
	var response externalSearchResponse
	if err := json.NewDecoder(recorder.Body).Decode(&response); err != nil {
		t.Fatal(err)
	}
	if response.Source != "muzsky" || len(response.Results) != 1 {
		t.Fatalf("unexpected backward-compatible response: %#v", response)
	}
	result := response.Results[0]
	if result.Source != "muzsky" || !result.InLibrary || result.LibraryTrackID != 7 || len(result.Variants) != 1 {
		t.Fatalf("unexpected result: %#v", result)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func TestSearchExternalRunsSourcesInParallel(t *testing.T) {
	started := make(chan string, 2)
	release := make(chan struct{})
	blocking := func(name string) sources.Searcher {
		return fakeExternalSearcher{search: func(ctx context.Context, query string) ([]sources.Result, error) {
			started <- name
			select {
			case <-release:
				return []sources.Result{}, nil
			case <-ctx.Done():
				return nil, ctx.Err()
			}
		}}
	}
	providers := map[string]sources.Provider{
		"first":  {Searcher: blocking("first")},
		"second": {Searcher: blocking("second")},
	}
	recorder := httptest.NewRecorder()
	done := make(chan struct{})
	go func() {
		SearchExternal(nil, providers, time.Second)(recorder, httptest.NewRequest(http.MethodGet, "/api/external/search?sources=first,second&q=test", nil))
		close(done)
	}()

	seen := map[string]bool{}
	for range 2 {
		select {
		case name := <-started:
			seen[name] = true
		case <-time.After(200 * time.Millisecond):
			t.Fatal("sources did not start concurrently")
		}
	}
	close(release)
	<-done
	if !seen["first"] || !seen["second"] || recorder.Code != http.StatusOK {
		t.Fatalf("unexpected parallel result: %#v, status %d", seen, recorder.Code)
	}
}

func TestSearchExternalReturnsPartialErrorsAndTimeouts(t *testing.T) {
	providers := map[string]sources.Provider{
		"working": {Searcher: resultsSearcher([]sources.Result{})},
		"failed": {Searcher: fakeExternalSearcher{search: func(context.Context, string) ([]sources.Result, error) {
			return nil, errors.New("offline")
		}}},
		"slow": {Searcher: fakeExternalSearcher{search: func(ctx context.Context, query string) ([]sources.Result, error) {
			<-ctx.Done()
			return nil, ctx.Err()
		}}},
	}
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/api/external/search?sources=working,failed,slow&q=test", nil)

	SearchExternal(nil, providers, 10*time.Millisecond)(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Fatalf("expected partial status 200, got %d", recorder.Code)
	}
	var response externalSearchResponse
	if err := json.NewDecoder(recorder.Body).Decode(&response); err != nil {
		t.Fatal(err)
	}
	if len(response.Errors) != 2 || response.Errors[0].Source != "failed" || response.Errors[1].Source != "slow" {
		t.Fatalf("unexpected partial errors: %#v", response.Errors)
	}
}

func TestSearchExternalSingleSourceErrorRemainsBadGateway(t *testing.T) {
	providers := map[string]sources.Provider{
		"muzsky": {Searcher: fakeExternalSearcher{search: func(context.Context, string) ([]sources.Result, error) {
			return nil, errors.New("offline")
		}}},
	}
	recorder := httptest.NewRecorder()
	SearchExternal(nil, providers, time.Second)(recorder, httptest.NewRequest(http.MethodGet, "/api/external/search?source=muzsky&q=Ado", nil))
	if recorder.Code != http.StatusBadGateway {
		t.Fatalf("expected status 502, got %d", recorder.Code)
	}
}

func TestSearchExternalReturnsLinkOnlySources(t *testing.T) {
	providers := map[string]sources.Provider{
		"bandcamp": {
			ExternalSearchURL: "https://bandcamp.com/search",
			QueryParameter:    "q",
			UnavailableReason: "no public catalog search API",
		},
	}
	recorder := httptest.NewRecorder()
	SearchExternal(nil, providers, time.Second)(recorder, httptest.NewRequest(http.MethodGet, "/api/external/search?source=bandcamp&q=Amazing+Grace", nil))
	if recorder.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", recorder.Code)
	}
	var response externalSearchResponse
	if err := json.NewDecoder(recorder.Body).Decode(&response); err != nil {
		t.Fatal(err)
	}
	if len(response.Results) != 0 || len(response.ExternalLinks) != 1 || response.ExternalLinks[0].URL != "https://bandcamp.com/search?q=Amazing+Grace" {
		t.Fatalf("unexpected external link response: %#v", response)
	}
}

func TestSearchExternalAppliesResultLimit(t *testing.T) {
	db, mock := libraryDatabase(t)
	defer db.Close()
	providers := map[string]sources.Provider{
		"muzsky": {Searcher: resultsSearcher([]sources.Result{
			{Title: "First", Artist: "Artist", Duration: "1:00", PageURL: "https://example.com/first"},
			{Title: "Second", Artist: "Artist", Duration: "2:00", PageURL: "https://example.com/second"},
		})},
	}
	recorder := httptest.NewRecorder()
	SearchExternal(db, providers, time.Second)(recorder, httptest.NewRequest(http.MethodGet, "/api/external/search?source=muzsky&q=test&limit=1", nil))
	if recorder.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", recorder.Code)
	}
	var response externalSearchResponse
	if err := json.NewDecoder(recorder.Body).Decode(&response); err != nil {
		t.Fatal(err)
	}
	if len(response.Results) != 1 || response.Results[0].Title != "First" {
		t.Fatalf("unexpected limited response: %#v", response.Results)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func TestSearchExternalValidation(t *testing.T) {
	providers := map[string]sources.Provider{"muzsky": {Searcher: resultsSearcher([]sources.Result{})}}
	for _, target := range []string{
		"/api/external/search?source=muzsky",
		"/api/external/search?q=Ado",
		"/api/external/search?source=unknown&q=Ado",
		"/api/external/search?source=muzsky&q=" + strings.Repeat("a", 201),
		"/api/external/search?source=muzsky&q=Ado&limit=0",
		"/api/external/search?source=muzsky&q=Ado&limit=51",
	} {
		recorder := httptest.NewRecorder()
		SearchExternal(nil, providers, time.Second)(recorder, httptest.NewRequest(http.MethodGet, target, nil))
		if recorder.Code != http.StatusBadRequest {
			t.Fatalf("expected status 400 for %s, got %d", target, recorder.Code)
		}
	}
}

func TestDeduplicateResultsPreservesVariantsAndPrefersDirectDownload(t *testing.T) {
	results := deduplicateResults([]sources.Result{
		{Title: "Amazing Grace", Artist: "Example Choir", Duration: "3:10", Source: "muzsky", PageURL: "https://muzsky.example", DownloadMethod: sources.DownloadExternal},
		{Title: "Amazing-Grace", Artist: "EXAMPLE CHOIR", Duration: "3:12", Source: "jamendo", PageURL: "https://jamendo.example", DownloadMethod: sources.DownloadDirect, DownloadAvailable: true},
		{Title: "Amazing Grace", Artist: "Example Choir", Duration: "4:00", Source: "different_recording", PageURL: "https://recording.example", DownloadMethod: sources.DownloadNone},
		{Title: "Amazing Grace", Artist: "Different Choir", Duration: "3:10", Source: "other", PageURL: "https://other.example", DownloadMethod: sources.DownloadNone},
	})
	if len(results) != 3 {
		t.Fatalf("expected three groups, got %#v", results)
	}
	if results[0].Source != "jamendo" || len(results[0].Variants) != 2 || !results[0].DownloadAvailable {
		t.Fatalf("variants were not preserved: %#v", results[0])
	}
}

func TestInterleaveResultsPreservesSourceOrder(t *testing.T) {
	combined := interleaveResults([]searchOutcome{
		{source: "first", results: []sources.Result{{Title: "A"}, {Title: "B"}}},
		{source: "second", results: []sources.Result{{Title: "C"}, {Title: "D"}}},
	})
	if len(combined) != 4 || combined[0].Title != "A" || combined[1].Title != "C" || combined[2].Title != "B" || combined[3].Title != "D" {
		t.Fatalf("unexpected interleaving: %#v", combined)
	}
}

func TestMarkLibraryRequiresArtistAndCompatibleDuration(t *testing.T) {
	results := []sources.Result{
		{Title: "Show!", Artist: "Ado", Duration: "3:10"},
		{Title: "Show", Artist: "Other", Duration: "3:10"},
		{Title: "Show", Artist: "Ado", Duration: "4:00"},
	}
	markLibrary(results, []models.Track{{ID: 3, Title: "show", Artist: "ADO", Duration: "3:11"}})
	if !results[0].InLibrary || results[0].LibraryTrackID != 3 || results[1].InLibrary || results[2].InLibrary {
		t.Fatalf("unexpected library matches: %#v", results)
	}
}

func libraryDatabase(t *testing.T, tracks ...models.Track) (*sql.DB, sqlmock.Sqlmock) {
	t.Helper()
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatal(err)
	}
	rows := sqlmock.NewRows([]string{
		"id", "title", "name", "duration", "cover_path", "audio_path",
		"file_size", "audio_format", "bit_depth", "sample_rate", "bitrate",
	})
	for _, track := range tracks {
		rows.AddRow(track.ID, track.Title, track.Artist, track.Duration, "", "/audio/test.mp3", nil, nil, nil, nil, nil)
	}
	mock.ExpectQuery("SELECT tracks.id").WillReturnRows(rows)
	return db, mock
}
