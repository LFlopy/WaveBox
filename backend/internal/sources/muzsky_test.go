package sources

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestMuzskySearch(t *testing.T) {
	suggestions := readSourceFixture(t, "testdata/suggestions.json")
	track := readSourceFixture(t, "testdata/track.html")

	var server *httptest.Server
	server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/suggest.php":
			if r.URL.Query().Get("q") != "Ado" {
				t.Fatalf("unexpected query: %s", r.URL.RawQuery)
			}
			w.Header().Set("Content-Type", "application/json")
			_, _ = w.Write([]byte(strings.ReplaceAll(string(suggestions), "{{BASE_URL}}", server.URL)))
		case "/music/ado-show":
			_, _ = w.Write(track)
		default:
			http.NotFound(w, r)
		}
	}))
	defer server.Close()

	source, err := NewMuzsky(server.Client(), server.URL, 0)
	if err != nil {
		t.Fatal(err)
	}
	results, err := source.Search(context.Background(), "Ado")
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 1 {
		t.Fatalf("expected one result, got %#v", results)
	}
	result := results[0]
	if result.Title != "Show" || result.Artist != "Ado" || result.Duration != "3:10" {
		t.Fatalf("unexpected result: %#v", result)
	}
	if result.Cover != server.URL+"/images/ado-show.webp" || result.PageURL != server.URL+"/music/ado-show" {
		t.Fatalf("unexpected URLs: %#v", result)
	}
}

func TestMuzskySearchEmpty(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("[]"))
	}))
	defer server.Close()

	source, err := NewMuzsky(server.Client(), server.URL, 0)
	if err != nil {
		t.Fatal(err)
	}
	results, err := source.Search(context.Background(), "missing")
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 0 {
		t.Fatalf("expected empty results, got %#v", results)
	}
}

func TestMuzskySearchChangedHTML(t *testing.T) {
	invalidTrack := readSourceFixture(t, "testdata/track-invalid.html")
	var server *httptest.Server
	server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/suggest.php" {
			_, _ = w.Write([]byte(`[{"type":"track","title":"Show","sub":"Ado","url":"` + server.URL + `/music/ado-show"}]`))
			return
		}
		_, _ = w.Write(invalidTrack)
	}))
	defer server.Close()

	source, err := NewMuzsky(server.Client(), server.URL, 0)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := source.Search(context.Background(), "Ado"); err == nil {
		t.Fatal("expected changed HTML error")
	}
}

func TestMuzskySearchChangedJSON(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`[{"type":"track","title":"Show","url":"/music/ado-show"}]`))
	}))
	defer server.Close()

	source, err := NewMuzsky(server.Client(), server.URL, 0)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := source.Search(context.Background(), "Ado"); err == nil {
		t.Fatal("expected changed JSON error")
	}
}

func TestMuzskySearchRejectsExternalTrackURL(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`[{"type":"track","title":"Show","sub":"Ado","url":"https://example.com/music/ado-show"}]`))
	}))
	defer server.Close()

	source, err := NewMuzsky(server.Client(), server.URL, 0)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := source.Search(context.Background(), "Ado"); err == nil {
		t.Fatal("expected external URL error")
	}
}

func TestMuzskySearchNetworkError(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	client := server.Client()
	server.Close()
	client.Timeout = 100 * time.Millisecond

	source, err := NewMuzsky(client, server.URL, 0)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := source.Search(context.Background(), "Ado"); err == nil {
		t.Fatal("expected network error")
	}
}
