package handlers

import (
	"encoding/json"
	"net/http"

	"wavebox/backend/internal/store"
)

func GetTracks(w http.ResponseWriter, r *http.Request) {
	tracks := store.GetTracks()

	w.Header().Set("Content-type", "application/json")

	if err := json.NewEncoder(w).Encode(tracks); err != nil {
		return
	}
}
