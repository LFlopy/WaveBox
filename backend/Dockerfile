FROM golang:alpine

WORKDIR /app/backend

COPY go.mod go.sum* ./
RUN go mod download

COPY . .

EXPOSE 8080

CMD [ "go", "run", "./cmd/api" ]



