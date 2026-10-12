package main

import (
	"log"
	"net/http"

	"wavebox/backend/internal/handlers"
)

func main() {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /health", handlers.Health)
	mux.HandleFunc("GET /api/tracks", handlers.GetTracks)

	log.Println("WaveBox API запущен на порту 8080")

	err := http.ListenAndServe(":8080", mux)
	if err != nil {
		log.Fatal(err)
	}
}
