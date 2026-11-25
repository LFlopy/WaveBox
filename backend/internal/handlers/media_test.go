package handlers

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestMediaFilesServing(t *testing.T) {
	directory := t.TempDir()
	album := filepath.Join(directory, "Album")
	if err := os.Mkdir(album, 0o700); err != nil {
		t.Fatal(err)
	}
	filename := filepath.Join(album, "Трек #1.FLAC")
	if err := os.WriteFile(filename, []byte("0123456789"), 0o600); err != nil {
		t.Fatal(err)
	}
	modified := time.Date(2025, time.January, 10, 9, 0, 0, 0, time.UTC)
	if err := os.Chtimes(filename, modified, modified); err != nil {
		t.Fatal(err)
	}
	mux := http.NewServeMux()
	mux.Handle("GET /audio/", http.StripPrefix("/audio/", MediaFiles(directory)))

	for _, test := range []struct {
		name       string
		method     string
		rangeValue string
		header     string
		condition  string
		status     int
		body       string
		byteRange  string
	}{
		{name: "full", method: "GET", status: 200, body: "0123456789"},
		{name: "head", method: "HEAD", status: 200},
		{name: "range", method: "GET", rangeValue: "bytes=2-5", status: 206, body: "2345", byteRange: "bytes 2-5/10"},
		{name: "suffix", method: "GET", rangeValue: "bytes=-3", status: 206, body: "789", byteRange: "bytes 7-9/10"},
		{name: "invalid range", method: "GET", rangeValue: "bytes=20-", status: 416, byteRange: "bytes */10"},
		{name: "cached", method: "GET", header: "If-Modified-Since", condition: modified.Format(http.TimeFormat), status: 304},
		{name: "changed range", method: "GET", rangeValue: "bytes=2-5", header: "If-Range", condition: modified.Add(-time.Hour).Format(http.TimeFormat), status: 200, body: "0123456789"},
	} {
		t.Run(test.name, func(t *testing.T) {
			req := httptest.NewRequest(test.method, "/audio/Album/%D0%A2%D1%80%D0%B5%D0%BA%20%231.FLAC", nil)
			if test.rangeValue != "" {
				req.Header.Set("Range", test.rangeValue)
			}
			if test.header != "" {
				req.Header.Set(test.header, test.condition)
			}
			result := httptest.NewRecorder()
			mux.ServeHTTP(result, req)
			if result.Code != test.status || result.Header().Get("Content-Range") != test.byteRange {
				t.Fatalf("status = %d, headers = %v", result.Code, result.Header())
			}
			if result.Code != 416 && result.Body.String() != test.body {
				t.Errorf("body = %q, want %q", result.Body.String(), test.body)
			}
			if (result.Code == 200 || result.Code == 206) &&
				(result.Header().Get("Content-Type") != "audio/flac" ||
					result.Header().Get("Accept-Ranges") != "bytes" ||
					result.Header().Get("X-Content-Type-Options") != "nosniff") {
				t.Errorf("unexpected media headers: %v", result.Header())
			}
		})
	}
}

func TestMediaFilesStayWithinDirectory(t *testing.T) {
	parent := t.TempDir()
	directory := filepath.Join(parent, "covers")
	if err := os.MkdirAll(filepath.Join(directory, "album.jpg"), 0o700); err != nil {
		t.Fatal(err)
	}
	outside := filepath.Join(parent, "private.jpg")
	if err := os.WriteFile(outside, []byte("outside"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(directory, "page.html"), []byte("<script></script>"), 0o600); err != nil {
		t.Fatal(err)
	}

	handler := MediaFiles(directory)
	for _, name := range []string{"/", "/album.jpg", "/missing.jpg", "/page.html", "/../private.jpg"} {
		result := httptest.NewRecorder()
		handler.ServeHTTP(result, httptest.NewRequest(http.MethodGet, name, nil))
		if result.Code != http.StatusNotFound {
			t.Errorf("%s: got %d, want 404", name, result.Code)
		}
	}

	if err := os.Symlink("../private.jpg", filepath.Join(directory, "linked.jpg")); err != nil {
		t.Skipf("symbolic links unavailable: %v", err)
	}
	result := httptest.NewRecorder()
	handler.ServeHTTP(result, httptest.NewRequest(http.MethodGet, "/linked.jpg", nil))
	if result.Code != http.StatusNotFound {
		t.Errorf("external symbolic link: got %d, want 404", result.Code)
	}
}
