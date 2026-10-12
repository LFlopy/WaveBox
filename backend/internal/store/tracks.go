package store

import "wavebox/backend/internal/models"

func GetTracks() []models.Track {
	return []models.Track{
		{
			ID:       1,
			Title:    "Track one",
			Artist:   "Artist one",
			Duration: "3:00",
			Cover:    "/covers/505.JPG",
			AudioURL: "/audio/505.mp3",
		},
		{
			ID:       2,
			Title:    "Track two",
			Artist:   "Artist two",
			Duration: "2:45",
			Cover:    "/covers/101.JPG",
			AudioURL: "/audio/101.mp3",
		},
	}
}
