package main

import (
	"database/sql"
	"log"
	"net/http"
	"os"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
	"wavebox/backend/internal/handlers"
	"wavebox/backend/internal/sources"
)

func main() {
	databaseURL := os.Getenv("DATABASE_URL")
	if databaseURL == "" {
		log.Fatal("DATABASE_URL is required")
	}

	db, err := sql.Open("pgx", databaseURL)
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()

	if err := db.Ping(); err != nil {
		log.Fatal(err)
	}
	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	mux := http.NewServeMux()
	muzsky, err := sources.NewMuzsky(nil, "https://muzsky.net", 500*time.Millisecond)
	if err != nil {
		log.Fatal(err)
	}

	mux.HandleFunc("GET /health", handlers.Health)
	mux.HandleFunc("GET /api/tracks", handlers.GetTracks(db))
	mux.HandleFunc("GET /api/external/search", handlers.SearchExternal(map[string]sources.Searcher{
		"muzsky": muzsky,
	}))

	audioServer := http.FileServer(http.Dir("../tracks/audio"))
	coverServer := http.FileServer(http.Dir("../tracks/covers"))

	mux.Handle(
		"GET /audio/",
		http.StripPrefix("/audio/", audioServer),
	)

	mux.Handle(
		"GET /covers/",
		http.StripPrefix("/covers/", coverServer),
	)

	log.Printf("WaveBox API запущен на порту %s", port)

	err = http.ListenAndServe(":"+port, mux)
	if err != nil {
		log.Fatal(err)
	}
}
