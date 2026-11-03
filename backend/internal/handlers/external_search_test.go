package handlers

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"wavebox/backend/internal/sources"
)

type fakeExternalSearcher struct {
	results []sources.Result
	err     error
}

func (f fakeExternalSearcher) Search(context.Context, string) ([]sources.Result, error) {
	return f.results, f.err
}

func TestSearchExternal(t *testing.T) {
	searchers := map[string]sources.Searcher{
		"muzsky": fakeExternalSearcher{results: []sources.Result{{Title: "Show", Artist: "Ado", Duration: "3:10"}}},
	}
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/api/external/search?source=muzsky&q=Ado", nil)

	SearchExternal(searchers)(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", recorder.Code)
	}
	if recorder.Header().Get("Content-Type") != "application/json" {
		t.Fatalf("unexpected content type: %s", recorder.Header().Get("Content-Type"))
	}
	var response externalSearchResponse
	if err := json.NewDecoder(recorder.Body).Decode(&response); err != nil {
		t.Fatal(err)
	}
	if response.Source != "muzsky" || len(response.Results) != 1 || response.Results[0].Title != "Show" {
		t.Fatalf("unexpected response: %#v", response)
	}
}

func TestSearchExternalValidation(t *testing.T) {
	searchers := map[string]sources.Searcher{"muzsky": fakeExternalSearcher{}}
	for _, target := range []string{
		"/api/external/search?source=muzsky",
		"/api/external/search?q=Ado",
		"/api/external/search?source=unknown&q=Ado",
		"/api/external/search?source=muzsky&q=" + strings.Repeat("a", 201),
	} {
		recorder := httptest.NewRecorder()
		SearchExternal(searchers)(recorder, httptest.NewRequest(http.MethodGet, target, nil))
		if recorder.Code != http.StatusBadRequest {
			t.Fatalf("expected status 400 for %s, got %d", target, recorder.Code)
		}
	}
}

func TestSearchExternalSourceError(t *testing.T) {
	searchers := map[string]sources.Searcher{
		"muzsky": fakeExternalSearcher{err: errors.New("offline")},
	}
	recorder := httptest.NewRecorder()
	request := httptest.NewRequest(http.MethodGet, "/api/external/search?source=muzsky&q=Ado", nil)

	SearchExternal(searchers)(recorder, request)

	if recorder.Code != http.StatusBadGateway {
		t.Fatalf("expected status 502, got %d", recorder.Code)
	}
}
