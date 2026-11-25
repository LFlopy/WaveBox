package store

import (
	"context"
	"database/sql"

	"wavebox/backend/internal/models"
)

const selectTracks = `
		SELECT tracks.id, tracks.title, artists.name, tracks.duration,
		       tracks.cover_path, tracks.audio_path, tracks.file_size,
		       tracks.audio_format, tracks.bit_depth, tracks.sample_rate,
		       tracks.bitrate
		FROM tracks
		JOIN artists ON artists.id = tracks.artist_id
`

func GetTracks(ctx context.Context, db *sql.DB) ([]models.Track, error) {
	return queryTracks(ctx, db, selectTracks+" ORDER BY tracks.id")
}

func GetTrack(ctx context.Context, db *sql.DB, id int) (models.Track, error) {
	tracks, err := queryTracks(ctx, db, selectTracks+" WHERE tracks.id = $1", id)
	if err != nil {
		return models.Track{}, err
	}
	if len(tracks) == 0 {
		return models.Track{}, sql.ErrNoRows
	}
	return tracks[0], nil
}

func SearchTracks(ctx context.Context, db *sql.DB, query string, count, offset int) ([]models.Track, error) {
	return queryTracks(ctx, db, selectTracks+`
		WHERE $1 = '' OR strpos(lower(tracks.title || ' ' || artists.name), lower($1)) > 0
		ORDER BY tracks.id LIMIT $2 OFFSET $3
	`, query, count, offset)
}

func queryTracks(ctx context.Context, db *sql.DB, query string, args ...any) ([]models.Track, error) {
	rows, err := db.QueryContext(ctx, query, args...)
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
			&track.FileSize,
			&track.Format,
			&track.BitDepth,
			&track.SampleRate,
			&track.Bitrate,
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
