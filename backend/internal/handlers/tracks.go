package handlers

import (
	"database/sql"
	"encoding/json"
	"log"
	"net/http"

	"wavebox/backend/internal/store"
)

func GetTracks(db *sql.DB) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		tracks, err := store.GetTracks(r.Context(), db)
		if err != nil {
			log.Printf("get tracks: %v", err)
			http.Error(w, "failed to load tracks", http.StatusInternalServerError)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(tracks); err != nil {
			log.Printf("encode tracks: %v", err)
		}
	}
}
