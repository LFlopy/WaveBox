package handlers

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestGetTracks(t *testing.T) {
	request := httptest.NewRequest(http.MethodGet, "/api/tracks", nil)
	recorder := httptest.NewRecorder()

	GetTracks(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", recorder.Code)
	}
}
