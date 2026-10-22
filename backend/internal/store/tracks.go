package store

import "wavebox/backend/internal/models"

func GetTracks() []models.Track {
	return []models.Track{
		{
			ID:       1,
			Title:    "Show",
			Artist:   "Ado",
			Duration: "3:10",
			Cover:    "/covers/ado-show.JPG",
			AudioURL: "/audio/ado-show.mp3",
		},
		{
			ID:       2,
			Title:    "Usseewa",
			Artist:   "Ado",
			Duration: "3:25",
			Cover:    "/covers/ado-usseewa.JPG",
			AudioURL: "/audio/ado-usseewa.mp3",
		},
	}
}
