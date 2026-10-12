package models

type Track struct {
	ID       int    `json:"id"`
	Title    string `json:"title"`
	Artist   string `json:"artist"`
	Duration string `json:"duration"`
	Cover    string `json:"cover"`
	AudioURL string `json:"audioUrl"`
}
