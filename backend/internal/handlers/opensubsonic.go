package handlers

import (
	"crypto/sha256"
	"crypto/subtle"
	"database/sql"
	"encoding/json"
	"encoding/xml"
	"errors"
	"log"
	"net/http"
	"net/url"
	"path"
	"strconv"
	"strings"

	"wavebox/backend/internal/models"
	"wavebox/backend/internal/store"
)

type subsonicResponse struct {
	XMLName       xml.Name            `json:"-" xml:"subsonic-response"`
	Namespace     string              `json:"-" xml:"xmlns,attr"`
	Status        string              `json:"status" xml:"status,attr"`
	Version       string              `json:"version" xml:"version,attr"`
	ServerVersion string              `json:"serverVersion" xml:"serverVersion,attr"`
	Type          string              `json:"type" xml:"type,attr"`
	Open          bool                `json:"openSubsonic" xml:"openSubsonic,attr"`
	Extensions    []subsonicExtension `json:"openSubsonicExtensions,omitempty" xml:"-"`
	TokenInfo     *subsonicTokenInfo  `json:"tokenInfo,omitempty" xml:"tokenInfo,omitempty"`
	Song          *subsonicSong       `json:"song,omitempty" xml:"song,omitempty"`
	Search        *subsonicSearch     `json:"searchResult3,omitempty" xml:"searchResult3,omitempty"`
	Error         *subsonicError      `json:"error,omitempty" xml:"error,omitempty"`
}

type subsonicExtension struct {
	Name     string `json:"name"`
	Versions []int  `json:"versions"`
}

type subsonicTokenInfo struct {
	Username string `json:"username" xml:"username,attr"`
}

type subsonicError struct {
	Code    int    `json:"code" xml:"code,attr"`
	Message string `json:"message" xml:"message,attr"`
}

type subsonicSearch struct {
	Songs []subsonicSong `json:"song" xml:"song"`
}

type subsonicSong struct {
	ID          string `json:"id" xml:"id,attr"`
	Title       string `json:"title" xml:"title,attr"`
	Artist      string `json:"artist" xml:"artist,attr"`
	IsDir       bool   `json:"isDir" xml:"isDir,attr"`
	IsVideo     bool   `json:"isVideo" xml:"isVideo,attr"`
	Type        string `json:"type" xml:"type,attr"`
	Duration    int    `json:"duration,omitempty" xml:"duration,attr,omitempty"`
	CoverArt    string `json:"coverArt,omitempty" xml:"coverArt,attr,omitempty"`
	Suffix      string `json:"suffix,omitempty" xml:"suffix,attr,omitempty"`
	ContentType string `json:"contentType,omitempty" xml:"contentType,attr,omitempty"`
	Size        *int64 `json:"size,omitempty" xml:"size,attr,omitempty"`
	BitRate     int    `json:"bitRate,omitempty" xml:"bitRate,attr,omitempty"`
}

func OpenSubsonic(db *sql.DB, key, audioDir, coversDir string) http.HandlerFunc {
	expectedKey := sha256.Sum256([]byte(key))
	return func(w http.ResponseWriter, r *http.Request) {
		if key == "" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Cache-Control", "private, no-store")
		w.Header().Set("Referrer-Policy", "no-referrer")
		query := r.URL.Query()
		endpoint := strings.TrimSuffix(r.PathValue("endpoint"), ".view")
		format := query.Get("f")
		response := subsonicResponse{
			Namespace: "http://subsonic.org/restapi", Status: "ok",
			Version: "1.16.1", Type: "WaveBox", ServerVersion: "0.1.0", Open: true,
		}
		write := func() {
			if format == "json" {
				w.Header().Set("Content-Type", "application/json")
				if err := json.NewEncoder(w).Encode(map[string]subsonicResponse{"subsonic-response": response}); err != nil {
					log.Printf("encode OpenSubsonic JSON: %v", err)
				}
				return
			}
			w.Header().Set("Content-Type", "text/xml; charset=utf-8")
			if err := xml.NewEncoder(w).Encode(response); err != nil {
				log.Printf("encode OpenSubsonic XML: %v", err)
			}
		}
		fail := func(code int, message string) {
			if endpoint == "stream" || endpoint == "getCoverArt" {
				format = "xml"
			}
			response.Status = "failed"
			response.Error = &subsonicError{Code: code, Message: message}
			write()
		}
		if format != "" && format != "json" && format != "xml" {
			fail(0, "Unsupported response format")
			return
		}
		if endpoint == "getOpenSubsonicExtensions" {
			format = "json"
			response.Extensions = []subsonicExtension{{Name: "apiKeyAuthentication", Versions: []int{1}}}
			write()
			return
		}
		if query.Has("apiKey") && (len(query["apiKey"]) != 1 || query.Has("u") || query.Has("p") || query.Has("t") || query.Has("s")) {
			fail(43, "Multiple conflicting authentication mechanisms provided")
			return
		}
		if query.Has("t") || query.Has("s") {
			fail(41, "Token authentication is not supported")
			return
		}
		if query.Has("u") || query.Has("p") {
			fail(42, "Provided authentication mechanism is not supported")
			return
		}
		if !query.Has("apiKey") {
			fail(10, "An API key is required")
			return
		}
		actualKey := sha256.Sum256([]byte(query.Get("apiKey")))
		if subtle.ConstantTimeCompare(expectedKey[:], actualKey[:]) != 1 {
			fail(44, "Invalid API key")
			return
		}

		switch endpoint {
		case "ping":
			write()
		case "tokenInfo":
			response.TokenInfo = &subsonicTokenInfo{Username: "wavebox"}
			write()
		case "search3":
			search := strings.TrimSpace(query.Get("query"))
			count, countOK := subsonicNumber(query.Get("songCount"), 20, 100)
			offset, offsetOK := subsonicNumber(query.Get("songOffset"), 0, 10000)
			if !query.Has("query") || len(search) > 200 || !countOK || !offsetOK {
				fail(10, "Invalid search parameters")
				return
			}
			response.Search = &subsonicSearch{Songs: []subsonicSong{}}
			if count > 0 {
				tracks, err := store.SearchTracks(r.Context(), db, search, count, offset)
				if err != nil {
					log.Printf("OpenSubsonic track search: %v", err)
					fail(0, "Catalog unavailable")
					return
				}
				for _, track := range tracks {
					response.Search.Songs = append(response.Search.Songs, makeSubsonicSong(track))
				}
			}
			write()
		case "getSong", "stream", "getCoverArt":
			if endpoint == "stream" {
				maxRate, ok := subsonicNumber(query.Get("maxBitRate"), 0, 10000)
				if !ok || maxRate != 0 || (query.Get("format") != "" && query.Get("format") != "raw") {
					fail(0, "Only original audio is available")
					return
				}
			}
			id, err := strconv.Atoi(query.Get("id"))
			if err != nil || id < 1 {
				fail(10, "A valid track id is required")
				return
			}
			track, err := store.GetTrack(r.Context(), db, id)
			if errors.Is(err, sql.ErrNoRows) {
				fail(70, "Track not found")
				return
			}
			if err != nil {
				log.Printf("OpenSubsonic track lookup: %v", err)
				fail(0, "Catalog unavailable")
				return
			}
			if endpoint == "getSong" {
				song := makeSubsonicSong(track)
				response.Song = &song
				write()
				return
			}
			if endpoint == "stream" {
				if !serveTrackMedia(w, r, track.AudioURL, "/audio/", audioDir) {
					fail(70, "Audio file not found")
				}
				return
			}
			if !serveTrackMedia(w, r, track.Cover, "/covers/", coversDir) {
				fail(70, "Cover not found")
			}
		default:
			fail(0, "Unsupported endpoint")
		}
	}
}

func subsonicNumber(value string, fallback, max int) (int, bool) {
	if value == "" {
		return fallback, true
	}
	number, err := strconv.Atoi(value)
	return number, err == nil && number >= 0 && number <= max
}

func serveTrackMedia(w http.ResponseWriter, r *http.Request, location, prefix, directory string) bool {
	parsed, err := url.Parse(location)
	if err != nil || parsed.IsAbs() || parsed.Host != "" || parsed.RawQuery != "" || parsed.Fragment != "" {
		return false
	}
	name, ok := strings.CutPrefix(parsed.Path, prefix)
	return ok && serveMedia(w, r, directory, name)
}

func makeSubsonicSong(track models.Track) subsonicSong {
	song := subsonicSong{
		ID: strconv.Itoa(track.ID), Title: track.Title, Artist: track.Artist, Type: "music", Size: track.FileSize,
	}
	if track.Cover != "" {
		song.CoverArt = song.ID
	}
	if parsed, err := url.Parse(track.AudioURL); err == nil {
		extension := strings.ToLower(path.Ext(parsed.Path))
		song.Suffix = strings.TrimPrefix(extension, ".")
		song.ContentType = mediaTypes[extension]
	}
	seconds, ok := durationSeconds(track.Duration)
	if ok {
		song.Duration = seconds
	}
	if track.Bitrate != nil {
		song.BitRate = *track.Bitrate / 1000
	}
	return song
}
