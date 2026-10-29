package models

type Track struct {
	ID         int     `json:"id"`
	Title      string  `json:"title"`
	Artist     string  `json:"artist"`
	Duration   string  `json:"duration"`
	Cover      string  `json:"cover"`
	AudioURL   string  `json:"audioUrl"`
	FileSize   *int64  `json:"fileSize,omitempty"`
	Format     *string `json:"format,omitempty"`
	BitDepth   *int    `json:"bitDepth,omitempty"`
	SampleRate *int    `json:"sampleRate,omitempty"`
	Bitrate    *int    `json:"bitrate,omitempty"`
}
