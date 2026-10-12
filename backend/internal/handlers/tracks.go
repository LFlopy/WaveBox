package handlers

import {
	"encoding/json"
	"net/http"
}


type Track struct {
	
	ID				int			'json:"ID'
	Title			string	'json:"Title'
	Artist		string	'json:"Artist'
	Duration	int			'json:"Duration'
}

func GetTracs(w	http.ResponseWriter, r *http.Request) {
	tracks := []Track{
		{ID: 1, Title: "Track one", Artist: "Artist one", Duration: 180},
		{ID: 2, Title: "Track two", Artist: "artist two", Duration: 360},
	}

	w.Header().set("Content-type", "application/json")
	json.NewEncoder(w).Encode(tracks)
}
