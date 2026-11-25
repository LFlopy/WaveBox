package handlers

import (
	"io/fs"
	"net/http"
	"os"
	"path"
	"path/filepath"
	"strings"
)

var mediaTypes = map[string]string{
	".mp3":  "audio/mpeg",
	".flac": "audio/flac",
	".ogg":  "audio/ogg",
	".oga":  "audio/ogg",
	".opus": "audio/ogg",
	".aac":  "audio/aac",
	".m4a":  "audio/mp4",
	".wav":  "audio/wav",
	".jpg":  "image/jpeg",
	".jpeg": "image/jpeg",
	".png":  "image/png",
	".webp": "image/webp",
	".gif":  "image/gif",
	".avif": "image/avif",
	".bmp":  "image/bmp",
}

func MediaFiles(directory string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		name := strings.TrimPrefix(r.URL.Path, "/")
		contentType := mediaTypes[strings.ToLower(path.Ext(name))]
		if contentType == "" || !fs.ValidPath(name) || strings.Contains(name, "\\") {
			http.NotFound(w, r)
			return
		}

		root, err := os.OpenRoot(directory)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		defer root.Close()

		localName := filepath.FromSlash(name)
		info, err := root.Stat(localName)
		if err != nil || !info.Mode().IsRegular() {
			http.NotFound(w, r)
			return
		}
		file, err := root.Open(localName)
		if err != nil {
			http.NotFound(w, r)
			return
		}
		defer file.Close()
		info, err = file.Stat()
		if err != nil || !info.Mode().IsRegular() {
			http.NotFound(w, r)
			return
		}

		w.Header().Set("Content-Type", contentType)
		w.Header().Set("X-Content-Type-Options", "nosniff")
		http.ServeContent(w, r, path.Base(name), info.ModTime(), file)
	})
}
