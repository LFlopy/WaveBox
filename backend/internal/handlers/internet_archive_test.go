package handlers

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"wavebox/backend/internal/sources"
)

type archiveFileListerStub struct {
	item sources.ArchiveItemFiles
	err  error
}

func (stub archiveFileListerStub) Files(context.Context, string) (sources.ArchiveItemFiles, error) {
	return stub.item, stub.err
}

func TestInternetArchiveFilesHandler(t *testing.T) {
	handler := InternetArchiveFiles(archiveFileListerStub{item: sources.ArchiveItemFiles{Identifier: "licensed-audio", Files: []sources.ArchiveAudioFile{}}}, time.Second)
	recorder := httptest.NewRecorder()
	handler(recorder, httptest.NewRequest(http.MethodGet, "/api/external/internet-archive/files?identifier=licensed-audio", nil))
	if recorder.Code != http.StatusOK || recorder.Body.String() != "{\"identifier\":\"licensed-audio\",\"title\":\"\",\"artist\":\"\",\"files\":[]}\n" {
		t.Fatalf("unexpected response: %d %s", recorder.Code, recorder.Body.String())
	}
}

func TestInternetArchiveFilesHandlerErrors(t *testing.T) {
	for _, test := range []struct {
		name    string
		target  string
		lister  archiveFileLister
		status  int
	}{
		{name: "invalid identifier", target: "/api/external/internet-archive/files?identifier=../bad", lister: archiveFileListerStub{}, status: http.StatusBadRequest},
		{name: "upstream error", target: "/api/external/internet-archive/files?identifier=licensed-audio", lister: archiveFileListerStub{err: errors.New("offline")}, status: http.StatusBadGateway},
	} {
		t.Run(test.name, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			InternetArchiveFiles(test.lister, time.Second)(recorder, httptest.NewRequest(http.MethodGet, test.target, nil))
			if recorder.Code != test.status {
				t.Fatalf("expected %d, got %d", test.status, recorder.Code)
			}
		})
	}
}
