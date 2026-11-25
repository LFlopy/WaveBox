package handlers

import (
	"encoding/json"
	"encoding/xml"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/DATA-DOG/go-sqlmock"
)

const testSubsonicKey = "synthetic-test-key-not-a-credential"

func TestOpenSubsonicAuthentication(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /rest/{endpoint}", OpenSubsonic(nil, testSubsonicKey, "", ""))

	for _, test := range []struct {
		target string
		code   int
		body   string
	}{
		{target: "getOpenSubsonicExtensions.view", body: "apiKeyAuthentication"},
		{target: "ping?f=json", code: 10},
		{target: "ping?f=json&apiKey=wrong", code: 44},
		{target: "ping?f=json&apiKey=" + testSubsonicKey + "&u=alice", code: 43},
		{target: "ping?f=json&apiKey=" + testSubsonicKey + "&apiKey=wrong", code: 43},
		{target: "ping?f=json&s=salt&t=digest", code: 41},
		{target: "ping?f=json&u=alice&p=unused", code: 42},
		{target: "ping.view?f=json&apiKey=" + testSubsonicKey, body: "WaveBox"},
		{target: "tokenInfo?f=json&apiKey=" + testSubsonicKey, body: "username"},
		{target: "search3?f=json&query=x&songCount=101&apiKey=" + testSubsonicKey, code: 10},
	} {
		t.Run(test.target, func(t *testing.T) {
			result := httptest.NewRecorder()
			mux.ServeHTTP(result, httptest.NewRequest(http.MethodGet, "/rest/"+test.target, nil))
			if result.Code != 200 || result.Header().Get("Cache-Control") != "private, no-store" {
				t.Fatalf("status %d, headers %v", result.Code, result.Header())
			}
			var envelope map[string]subsonicResponse
			if err := json.Unmarshal(result.Body.Bytes(), &envelope); err != nil {
				t.Fatal(err)
			}
			response := envelope["subsonic-response"]
			if test.code != 0 && (response.Error == nil || response.Error.Code != test.code) {
				t.Fatalf("unexpected response: %+v", response)
			}
			if test.code == 0 && (response.Status != "ok" || !strings.Contains(result.Body.String(), test.body)) {
				t.Fatalf("unexpected response: %s", result.Body.String())
			}
		})
	}

	result := httptest.NewRecorder()
	mux.ServeHTTP(result, httptest.NewRequest(http.MethodGet, "/rest/stream?f=json&apiKey=wrong", nil))
	var response subsonicResponse
	if err := xml.Unmarshal(result.Body.Bytes(), &response); err != nil || response.Error == nil || response.Error.Code != 44 {
		t.Fatalf("unexpected stream error: %s (%v)", result.Body.String(), err)
	}

	result = httptest.NewRecorder()
	OpenSubsonic(nil, "", "", "")(result, httptest.NewRequest(http.MethodGet, "/rest/ping", nil))
	if result.Code != http.StatusNotFound {
		t.Fatalf("disabled adapter status = %d", result.Code)
	}
}

func TestOpenSubsonicSearchAndMedia(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	audio := t.TempDir()
	covers := t.TempDir()
	if err := os.WriteFile(filepath.Join(audio, "Track #1.flac"), []byte("0123456789"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(covers, "cover.png"), []byte("cover"), 0o600); err != nil {
		t.Fatal(err)
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /rest/{endpoint}", OpenSubsonic(db, testSubsonicKey, audio, covers))

	rows := func(file string) *sqlmock.Rows {
		return sqlmock.NewRows([]string{
			"id", "title", "name", "duration", "cover_path", "audio_path",
			"file_size", "audio_format", "bit_depth", "sample_rate", "bitrate",
		}).AddRow(7, "Track <1>", "Artist", "2:05", "/covers/cover.png", file, 10, "flac", 24, 44100, 256000)
	}

	mock.ExpectQuery("strpos").WithArgs("track", 5, 2).WillReturnRows(rows("/audio/Track%20%231.flac"))
	result := httptest.NewRecorder()
	mux.ServeHTTP(result, httptest.NewRequest(http.MethodGet, "/rest/search3?f=json&query=track&songCount=5&songOffset=2&apiKey="+testSubsonicKey, nil))
	var envelope map[string]subsonicResponse
	if err := json.Unmarshal(result.Body.Bytes(), &envelope); err != nil {
		t.Fatal(err)
	}
	search := envelope["subsonic-response"].Search
	if search == nil || len(search.Songs) != 1 || search.Songs[0].BitRate != 256 ||
		search.Songs[0].Duration != 125 || search.Songs[0].ID != "7" {
		t.Fatalf("unexpected results: %s", result.Body.String())
	}

	for _, test := range []struct {
		endpoint, file, contentType, body string
		status                            int
	}{
		{"getSong", "/audio/Track%20%231.flac", "text/xml; charset=utf-8", "Track &lt;1&gt;", 200},
		{"stream", "/audio/Track%20%231.flac", "audio/flac", "234", 206},
		{"getCoverArt", "/audio/Track%20%231.flac", "image/png", "cover", 200},
		{"stream", "/audio/%2e%2e/secret.flac", "text/xml; charset=utf-8", `code="70"`, 200},
	} {
		mock.ExpectQuery("WHERE tracks.id =").WithArgs(7).WillReturnRows(rows(test.file))
		request := httptest.NewRequest(http.MethodGet, "/rest/"+test.endpoint+".view?id=7&apiKey="+testSubsonicKey, nil)
		if test.status == 206 {
			request.Header.Set("Range", "bytes=2-4")
		}
		result := httptest.NewRecorder()
		mux.ServeHTTP(result, request)
		if result.Code != test.status || result.Header().Get("Content-Type") != test.contentType ||
			!strings.Contains(result.Body.String(), test.body) {
			t.Errorf("%s status %d, headers %v, body %s", test.endpoint, result.Code, result.Header(), result.Body.String())
		}
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}
