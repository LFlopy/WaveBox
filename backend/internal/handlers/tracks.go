package handlers

import (
	"encoding/json"
	"net/http"
)

type Track struct {
	ID       string `json:"ID"`
	Title    string `json:"Title"`
	Artist   string `json:"Artist"`
	Duration string `json:"Duration"`
	Cover    string `json:"cover`
	AudioUrl string `json:"audioUrl"`
}

func GetTracks(w http.ResponseWriter, r *http.Request) {
	tracks := []Track{
		{ID: "1", Title: "Track one", Artist: "Artist one", Duration: "180", Cover: "/covers/505.JPG", AudioUrl: "/audio/505.mp3"},
		{ID: "2", Title: "Track two", Artist: "artist two", Duration: "360", Cover: "/covers/101.JPG", AudioUrl: "/audio/101.mp3"},
	}

	w.Header().Set("Content-type", "application/json")
	json.NewEncoder(w).Encode(tracks)
}
