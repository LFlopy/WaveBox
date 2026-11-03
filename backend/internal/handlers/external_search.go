package handlers

import (
	"encoding/json"
	"log"
	"net/http"
	"strings"

	"wavebox/backend/internal/sources"
)

type externalSearchResponse struct {
	Source  string           `json:"source"`
	Results []sources.Result `json:"results"`
}

func SearchExternal(searchers map[string]sources.Searcher) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		sourceName := strings.TrimSpace(r.URL.Query().Get("source"))
		query := strings.TrimSpace(r.URL.Query().Get("q"))
		if sourceName == "" || query == "" || len(query) > 200 {
			http.Error(w, "source and q are required", http.StatusBadRequest)
			return
		}

		searcher, ok := searchers[sourceName]
		if !ok {
			http.Error(w, "unknown source", http.StatusBadRequest)
			return
		}

		results, err := searcher.Search(r.Context(), query)
		if err != nil {
			log.Printf("search external source %s: %v", sourceName, err)
			http.Error(w, "external source is unavailable", http.StatusBadGateway)
			return
		}

		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(externalSearchResponse{Source: sourceName, Results: results}); err != nil {
			log.Printf("encode external search: %v", err)
		}
	}
}
