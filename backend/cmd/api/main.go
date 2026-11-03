package main

import (
	"database/sql"
	"log"
	"net/http"
	"os"
	"strings"
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
	internetArchive, err := sources.NewInternetArchive(nil, "https://archive.org", 10)
	if err != nil {
		log.Fatal(err)
	}
	providers := map[string]sources.Provider{
		"muzsky":           {Searcher: muzsky},
		"internet_archive": {Searcher: internetArchive},
		"bandcamp": {
			ExternalSearchURL: "https://bandcamp.com/search",
			QueryParameter:    "q",
			UnavailableReason: "Bandcamp has no public catalog search API",
		},
		"qobuz": {
			ExternalSearchURL: "https://www.qobuz.com/us-en/shop",
			UnavailableReason: "Qobuz API credentials and approved access are required",
		},
		"free_music_archive": {
			ExternalSearchURL: "https://freemusicarchive.org/search/",
			QueryParameter:    "quicksearch",
			UnavailableReason: "Free Music Archive has shut down its public API and forbids unapproved search proxying",
		},
		"jamendo": {
			ExternalSearchURL: "https://www.jamendo.com/start",
			UnavailableReason: "JAMENDO_CLIENT_ID is required for official API access",
		},
	}
	if clientID := strings.TrimSpace(os.Getenv("JAMENDO_CLIENT_ID")); clientID != "" {
		jamendo, err := sources.NewJamendo(nil, "https://api.jamendo.com", clientID, 10)
		if err != nil {
			log.Fatal(err)
		}
		providers["jamendo"] = sources.Provider{Searcher: jamendo}
	}

	mux.HandleFunc("GET /health", handlers.Health)
	mux.HandleFunc("GET /api/tracks", handlers.GetTracks(db))
	mux.HandleFunc("GET /api/external/search", handlers.SearchExternal(db, providers, 12*time.Second))

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
