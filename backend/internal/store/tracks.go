package store

import (
	"context"
	"database/sql"

	"wavebox/backend/internal/models"
)

func GetTracks(ctx context.Context, db *sql.DB) ([]models.Track, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT tracks.id, tracks.title, artists.name, tracks.duration,
		       tracks.cover_path, tracks.audio_path
		FROM tracks
		JOIN artists ON artists.id = tracks.artist_id
		ORDER BY tracks.id
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	tracks := make([]models.Track, 0)
	for rows.Next() {
		var track models.Track
		if err := rows.Scan(
			&track.ID,
			&track.Title,
			&track.Artist,
			&track.Duration,
			&track.Cover,
			&track.AudioURL,
		); err != nil {
			return nil, err
		}
		tracks = append(tracks, track)
	}

	if err := rows.Err(); err != nil {
		return nil, err
	}

	return tracks, nil
}
