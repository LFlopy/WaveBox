package handlers

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"wavebox/backend/internal/sources"
)

type archiveFileLister interface {
	Files(context.Context, string) (sources.ArchiveItemFiles, error)
}

func InternetArchiveFiles(archive archiveFileLister, timeout time.Duration) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		identifier := strings.TrimSpace(r.URL.Query().Get("identifier"))
		if !sources.ValidArchiveIdentifier(identifier) {
			writeArchiveError(w, "invalid Internet Archive identifier", http.StatusBadRequest)
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), timeout)
		defer cancel()
		item, err := archive.Files(ctx, identifier)
		if err != nil {
			writeArchiveError(w, "Internet Archive metadata is unavailable", http.StatusBadGateway)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(item)
	}
}

func writeArchiveError(w http.ResponseWriter, message string, status int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": message})
}
