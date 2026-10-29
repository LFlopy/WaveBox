package handlers

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/DATA-DOG/go-sqlmock"
	"wavebox/backend/internal/models"
)

func TestGetTracks(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	rows := sqlmock.NewRows([]string{"id", "title", "name", "duration", "cover_path", "audio_path"}).
		AddRow(1, "Show", "Ado", "3:10", "/covers/ado-show.JPG", "/audio/ado-show.mp3")
	mock.ExpectQuery("SELECT tracks.id").WillReturnRows(rows)

	request := httptest.NewRequest(http.MethodGet, "/api/tracks", nil)
	recorder := httptest.NewRecorder()

	GetTracks(db)(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", recorder.Code)
	}

	var tracks []models.Track
	if err := json.NewDecoder(recorder.Body).Decode(&tracks); err != nil {
		t.Fatal(err)
	}
	if len(tracks) != 1 || tracks[0].AudioURL != "/audio/ado-show.mp3" {
		t.Fatalf("unexpected tracks: %#v", tracks)
	}
	if err := mock.ExpectationsWereMet(); err != nil {
		t.Fatal(err)
	}
}

func TestGetTracksDatabaseError(t *testing.T) {
	db, mock, err := sqlmock.New()
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()

	mock.ExpectQuery("SELECT tracks.id").WillReturnError(sql.ErrConnDone)
	recorder := httptest.NewRecorder()
	GetTracks(db)(recorder, httptest.NewRequest(http.MethodGet, "/api/tracks", nil))

	if recorder.Code != http.StatusInternalServerError {
		t.Fatalf("expected status 500, got %d", recorder.Code)
	}
}
