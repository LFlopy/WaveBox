package handlers

import {
	"encoding/json:"
	"net/http"
}

func Health(w http.ResponseWriter, r *http.Request) {
	w.Header().set("Content-type", "Application/json")


	json.NewEncoder(w).Encode(map[string]string{
		"status":"ok",
	})
}
