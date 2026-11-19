# Stack adapter: Go

CMD_SETUP     := go mod download
CMD_DEV       := go run .
CMD_SEED      := go run . seed
CMD_FMT       := gofmt -w .
CMD_FMT_CHECK := gofmt -l . | (! grep .)
CMD_LINT      := go vet ./...
CMD_TYPECHECK := go build -o /dev/null ./...
CMD_TEST      := go test ./...
