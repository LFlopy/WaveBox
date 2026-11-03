package sources

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestJamendoSearch(t *testing.T) {
	fixture := readSourceFixture(t, "testdata/jamendo.json")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v3.0/tracks/" {
			http.NotFound(w, r)
			return
		}
		parameters := r.URL.Query()
		if parameters.Get("client_id") != "client-id" || parameters.Get("search") != "Amazing Grace" || parameters.Get("limit") != "5" {
			t.Fatalf("unexpected parameters: %s", r.URL.RawQuery)
		}
		if parameters.Get("audiodlformat") != "mp32" {
			t.Fatalf("download format is not explicit: %s", r.URL.RawQuery)
		}
		_, _ = w.Write(fixture)
	}))
	defer server.Close()

	jamendo, err := NewJamendo(server.Client(), server.URL, "client-id", 5)
	if err != nil {
		t.Fatal(err)
	}
	results, err := jamendo.Search(context.Background(), "Amazing Grace")
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 2 {
		t.Fatalf("expected two results, got %#v", results)
	}
	first := results[0]
	if first.Duration != "3:10" || first.Format != "mp3" || first.Quality != "VBR (mp32)" {
		t.Fatalf("unexpected metadata: %#v", first)
	}
	if !first.DownloadAvailable || first.DownloadMethod != DownloadDirect || first.DownloadURL == "" {
		t.Fatalf("expected permitted direct download: %#v", first)
	}
	second := results[1]
	if second.DownloadAvailable || second.DownloadMethod != DownloadNone || second.Format != "" || second.DownloadURL != "" {
		t.Fatalf("download must remain unavailable: %#v", second)
	}
}

func TestJamendoAPIFailure(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"headers":{"status":"failed","code":11,"error_message":"suspended"},"results":[]}`))
	}))
	defer server.Close()
	jamendo, err := NewJamendo(server.Client(), server.URL, "client-id", 5)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := jamendo.Search(context.Background(), "test"); err == nil {
		t.Fatal("expected API failure")
	}
}
