package sources

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
)

func TestInternetArchiveSearch(t *testing.T) {
	fixture := readSourceFixture(t, "testdata/internet-archive.json")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/advancedsearch.php" {
			http.NotFound(w, r)
			return
		}
		if r.URL.Query().Get("q") != `mediatype:audio AND (title:"Amazing Grace" OR creator:"Amazing Grace")` {
			t.Fatalf("unexpected query: %s", r.URL.Query().Get("q"))
		}
		if r.URL.Query().Get("rows") != "5" || r.URL.Query().Get("output") != "json" {
			t.Fatalf("unexpected parameters: %s", r.URL.RawQuery)
		}
		_, _ = w.Write(fixture)
	}))
	defer server.Close()

	archive, err := NewInternetArchive(server.Client(), server.URL, 5)
	if err != nil {
		t.Fatal(err)
	}
	results, err := archive.Search(context.Background(), "Amazing Grace")
	if err != nil {
		t.Fatal(err)
	}
	if len(results) != 2 {
		t.Fatalf("expected two results, got %#v", results)
	}
	first := results[0]
	if first.Title != "Amazing Grace" || first.Artist != "Example Choir" || first.Format != "mp3" || first.Quality != "144Kbps MP3" {
		t.Fatalf("unexpected first result: %#v", first)
	}
	if first.Source != "internet_archive" || first.DownloadMethod != DownloadExternal || first.DownloadAvailable {
		t.Fatalf("unexpected availability: %#v", first)
	}
	if first.PageURL != server.URL+"/details/amazing-grace" || first.Cover != server.URL+"/services/img/amazing-grace" {
		t.Fatalf("unexpected URLs: %#v", first)
	}
	if results[1].Artist != "First Artist; Second Artist" || results[1].Format != "" {
		t.Fatalf("ambiguous formats must not be invented: %#v", results[1])
	}
}

func TestInternetArchiveRejectsInvalidResponse(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"response":{"docs":[{"title":"Missing identifier"}]}}`))
	}))
	defer server.Close()
	archive, err := NewInternetArchive(server.Client(), server.URL, 5)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := archive.Search(context.Background(), "test"); err == nil {
		t.Fatal("expected invalid response error")
	}
}

func TestInternetArchiveFiles(t *testing.T) {
	fixture := readSourceFixture(t, "testdata/internet-archive-metadata.json")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/metadata/licensed-audio" || r.URL.Query().Get("extended_err") != "1" {
			t.Fatalf("unexpected metadata request: %s", r.URL.String())
		}
		_, _ = w.Write(fixture)
	}))
	defer server.Close()
	archive, err := NewInternetArchive(server.Client(), server.URL, 5)
	if err != nil {
		t.Fatal(err)
	}
	item, err := archive.Files(context.Background(), "licensed-audio")
	if err != nil {
		t.Fatal(err)
	}
	if item.Identifier != "licensed-audio" || item.Artist != "Example Artist" || len(item.Files) != 3 {
		t.Fatalf("unexpected item: %#v", item)
	}
	if !item.Files[0].DownloadAvailable || item.Files[0].Format != "mp3" || item.Files[0].Size != 12345 {
		t.Fatalf("unexpected MP3: %#v", item.Files[0])
	}
	if item.Files[1].Title != "Licensed Item" || item.Files[1].Format != "flac" {
		t.Fatalf("unexpected FLAC: %#v", item.Files[1])
	}
	if item.Files[2].DownloadAvailable || item.Files[2].UnavailableReason == "" {
		t.Fatalf("private file must be unavailable: %#v", item.Files[2])
	}
}

func TestInternetArchiveFilesRequirePermissiveLicense(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"files":[{"name":"song.mp3","format":"VBR MP3","size":"5"}],"metadata":{"identifier":"unlicensed-audio","title":"Song","creator":"Artist","mediatype":"audio"}}`))
	}))
	defer server.Close()
	archive, err := NewInternetArchive(server.Client(), server.URL, 5)
	if err != nil {
		t.Fatal(err)
	}
	item, err := archive.Files(context.Background(), "unlicensed-audio")
	if err != nil {
		t.Fatal(err)
	}
	if len(item.Files) != 1 || item.Files[0].DownloadAvailable {
		t.Fatalf("unlicensed file must be unavailable: %#v", item.Files)
	}
}

func TestInternetArchiveFilesRejectInvalidIdentifier(t *testing.T) {
	archive, err := NewInternetArchive(http.DefaultClient, "https://archive.org", 5)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := archive.Files(context.Background(), "../private"); err == nil {
		t.Fatal("expected invalid identifier error")
	}
}

func TestArchiveQueryEscapesLuceneSyntax(t *testing.T) {
	query := archiveQuery(`artist "title"`)
	if !strings.Contains(query, `\"title\"`) {
		t.Fatalf("query was not escaped: %s", query)
	}
}

func readSourceFixture(t *testing.T, path string) []byte {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	return data
}
