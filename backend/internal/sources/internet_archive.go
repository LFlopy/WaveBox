package sources

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/url"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

type InternetArchive struct {
	baseURL *url.URL
	client  *http.Client
	limit   int
}

type archiveSearchResponse struct {
	Response struct {
		Docs []archiveDocument `json:"docs"`
	} `json:"response"`
}

type archiveDocument struct {
	Identifier string          `json:"identifier"`
	Title      string          `json:"title"`
	Creator    archiveCreators `json:"creator"`
	Formats    []string        `json:"format"`
}

type ArchiveAudioFile struct {
	Title             string `json:"title"`
	Artist            string `json:"artist"`
	Format            string `json:"format"`
	Quality           string `json:"quality"`
	Size              int64  `json:"size"`
	FileName          string `json:"fileName"`
	DownloadAvailable bool   `json:"downloadAvailable"`
	UnavailableReason string `json:"unavailableReason,omitempty"`
}

type ArchiveItemFiles struct {
	Identifier string             `json:"identifier"`
	Title      string             `json:"title"`
	Artist     string             `json:"artist"`
	LicenseURL string             `json:"licenseUrl,omitempty"`
	Rights     string             `json:"rights,omitempty"`
	Files      []ArchiveAudioFile `json:"files"`
}

type archiveMetadataResponse struct {
	Files    []archiveMetadataFile `json:"files"`
	Metadata archiveItemMetadata   `json:"metadata"`
	IsDark   archiveBool           `json:"is_dark"`
	Error    string                `json:"error"`
}

type archiveMetadataFile struct {
	Name    string      `json:"name"`
	Title   string      `json:"title"`
	Format  string      `json:"format"`
	Size    string      `json:"size"`
	Private archiveBool `json:"private"`
}

type archiveItemMetadata struct {
	Identifier       string          `json:"identifier"`
	Title            string          `json:"title"`
	Creator          archiveCreators `json:"creator"`
	MediaType        string          `json:"mediatype"`
	LicenseURL       string          `json:"licenseurl"`
	Rights           string          `json:"rights"`
	AccessRestricted archiveBool     `json:"access-restricted-item"`
}

type archiveBool bool

var archiveIdentifierPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$`)

func (value *archiveBool) UnmarshalJSON(data []byte) error {
	var boolean bool
	if err := json.Unmarshal(data, &boolean); err == nil {
		*value = archiveBool(boolean)
		return nil
	}
	var text string
	if err := json.Unmarshal(data, &text); err != nil {
		return err
	}
	boolean, err := strconv.ParseBool(text)
	if err != nil {
		return err
	}
	*value = archiveBool(boolean)
	return nil
}

type archiveCreators []string

func (creators *archiveCreators) UnmarshalJSON(data []byte) error {
	if string(data) == "null" {
		*creators = nil
		return nil
	}
	var single string
	if err := json.Unmarshal(data, &single); err == nil {
		*creators = []string{single}
		return nil
	}
	var multiple []string
	if err := json.Unmarshal(data, &multiple); err != nil {
		return err
	}
	*creators = multiple
	return nil
}

func NewInternetArchive(client *http.Client, rawBaseURL string, limit int) (*InternetArchive, error) {
	baseURL, err := url.Parse(rawBaseURL)
	if err != nil || baseURL.Scheme == "" || baseURL.Host == "" {
		return nil, errors.New("invalid Internet Archive base URL")
	}
	if client == nil {
		client = &http.Client{Timeout: 10 * time.Second}
	}
	if limit <= 0 {
		limit = 10
	}
	return &InternetArchive{baseURL: baseURL, client: client, limit: limit}, nil
}

func (archive *InternetArchive) Search(ctx context.Context, query string) ([]Result, error) {
	searchURL := archive.baseURL.ResolveReference(&url.URL{Path: "/advancedsearch.php"})
	parameters := searchURL.Query()
	parameters.Set("q", archiveQuery(query))
	for _, field := range []string{"identifier", "title", "creator", "format"} {
		parameters.Add("fl[]", field)
	}
	parameters.Set("rows", fmt.Sprintf("%d", archive.limit))
	parameters.Set("page", "1")
	parameters.Set("output", "json")
	searchURL.RawQuery = parameters.Encode()

	body, err := getJSON(ctx, archive.client, searchURL.String(), "Internet Archive")
	if err != nil {
		return nil, err
	}

	var payload archiveSearchResponse
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil, fmt.Errorf("%w: invalid Internet Archive JSON", ErrUnexpectedResponse)
	}
	results := make([]Result, 0, len(payload.Response.Docs))
	for _, document := range payload.Response.Docs {
		if strings.TrimSpace(document.Identifier) == "" || strings.TrimSpace(document.Title) == "" {
			return nil, fmt.Errorf("%w: incomplete Internet Archive result", ErrUnexpectedResponse)
		}
		format, quality := archiveFormat(document.Formats)
		results = append(results, Result{
			Title:          document.Title,
			Artist:         strings.Join(document.Creator, "; "),
			Cover:          archive.baseURL.ResolveReference(&url.URL{Path: "/services/img/" + document.Identifier}).String(),
			Source:         "internet_archive",
			PageURL:        archive.baseURL.ResolveReference(&url.URL{Path: "/details/" + document.Identifier}).String(),
			Format:         format,
			Quality:        quality,
			DownloadMethod: DownloadExternal,
		})
	}
	return results, nil
}

func (archive *InternetArchive) Files(ctx context.Context, identifier string) (ArchiveItemFiles, error) {
	identifier = strings.TrimSpace(identifier)
	if !ValidArchiveIdentifier(identifier) {
		return ArchiveItemFiles{}, errors.New("invalid Internet Archive identifier")
	}
	metadataURL := archive.baseURL.ResolveReference(&url.URL{Path: "/metadata/" + identifier})
	parameters := metadataURL.Query()
	parameters.Set("extended_err", "1")
	metadataURL.RawQuery = parameters.Encode()
	body, err := getJSON(ctx, archive.client, metadataURL.String(), "Internet Archive metadata")
	if err != nil {
		return ArchiveItemFiles{}, err
	}
	if strings.TrimSpace(string(body)) == "[]" {
		return ArchiveItemFiles{}, fmt.Errorf("%w: Internet Archive item not found", ErrUnexpectedResponse)
	}
	var payload archiveMetadataResponse
	if err := json.Unmarshal(body, &payload); err != nil {
		return ArchiveItemFiles{}, fmt.Errorf("%w: invalid Internet Archive metadata JSON", ErrUnexpectedResponse)
	}
	if payload.Error != "" {
		return ArchiveItemFiles{}, fmt.Errorf("%w: Internet Archive metadata error", ErrUnexpectedResponse)
	}
	if payload.Metadata.Identifier != identifier || payload.Metadata.MediaType != "audio" {
		return ArchiveItemFiles{}, fmt.Errorf("%w: incomplete Internet Archive metadata", ErrUnexpectedResponse)
	}

	artist := strings.Join(payload.Metadata.Creator, "; ")
	item := ArchiveItemFiles{
		Identifier: identifier,
		Title:      strings.TrimSpace(payload.Metadata.Title),
		Artist:     artist,
		LicenseURL: strings.TrimSpace(payload.Metadata.LicenseURL),
		Rights:     strings.TrimSpace(payload.Metadata.Rights),
		Files:      make([]ArchiveAudioFile, 0),
	}
	licenseAllowed := permittedArchiveLicense(item.LicenseURL)
	itemRestricted := bool(payload.IsDark) || bool(payload.Metadata.AccessRestricted)
	for _, file := range payload.Files {
		format, quality := archiveAudioFileFormat(file.Name, file.Format)
		if format == "" {
			continue
		}
		size, sizeErr := strconv.ParseInt(file.Size, 10, 64)
		available := true
		reason := ""
		switch {
		case !safeArchiveFileName(file.Name):
			available, reason = false, "unsafe file name"
		case sizeErr != nil || size <= 0:
			available, reason = false, "file size is unavailable"
		case itemRestricted || bool(file.Private):
			available, reason = false, "item or file is access-restricted"
		case !licenseAllowed:
			available, reason = false, "no recognized permissive license is declared"
		}
		if sizeErr != nil {
			size = 0
		}
		title := strings.TrimSpace(file.Title)
		if title == "" {
			title = item.Title
		}
		item.Files = append(item.Files, ArchiveAudioFile{
			Title:             title,
			Artist:            artist,
			Format:            format,
			Quality:           quality,
			Size:              size,
			FileName:          file.Name,
			DownloadAvailable: available,
			UnavailableReason: reason,
		})
	}
	return item, nil
}

func ValidArchiveIdentifier(identifier string) bool {
	return archiveIdentifierPattern.MatchString(identifier)
}

func archiveAudioFileFormat(name, quality string) (string, string) {
	extension := strings.ToLower(filepath.Ext(name))
	lowerQuality := strings.ToLower(strings.TrimSpace(quality))
	switch {
	case extension == ".mp3" && strings.Contains(lowerQuality, "mp3") && !strings.Contains(lowerQuality, "m3u"):
		return "mp3", strings.TrimSpace(quality)
	case extension == ".flac" && strings.Contains(lowerQuality, "flac"):
		return "flac", strings.TrimSpace(quality)
	default:
		return "", ""
	}
}

func safeArchiveFileName(name string) bool {
	name = strings.TrimSpace(name)
	return name != "" && name != "." && name != ".." && !strings.ContainsAny(name, "/\\\x00")
}

func permittedArchiveLicense(raw string) bool {
	licenseURL, err := url.Parse(strings.TrimSpace(raw))
	if err != nil || (licenseURL.Scheme != "http" && licenseURL.Scheme != "https") {
		return false
	}
	host := strings.ToLower(licenseURL.Hostname())
	if host != "creativecommons.org" && host != "www.creativecommons.org" {
		return false
	}
	path := strings.ToLower(strings.TrimSuffix(licenseURL.Path, "/"))
	return strings.HasPrefix(path, "/licenses/") || path == "/publicdomain/zero/1.0" || path == "/publicdomain/mark/1.0"
}

func archiveQuery(query string) string {
	escaped := strings.NewReplacer(`\`, `\\`, `"`, `\"`).Replace(strings.TrimSpace(query))
	return fmt.Sprintf(`mediatype:audio AND (title:"%s" OR creator:"%s")`, escaped, escaped)
}

func archiveFormat(formats []string) (string, string) {
	found := make(map[string]string)
	for _, value := range formats {
		lower := strings.ToLower(value)
		switch {
		case strings.Contains(lower, "flac"):
			found["flac"] = value
		case strings.Contains(lower, "mp3") && !strings.Contains(lower, "m3u"):
			found["mp3"] = value
		case strings.Contains(lower, "ogg"):
			found["ogg"] = value
		case strings.Contains(lower, "mpeg-4 audio"):
			found["m4a"] = value
		}
	}
	if len(found) != 1 {
		return "", ""
	}
	for format, quality := range found {
		return format, quality
	}
	return "", ""
}
