# Stack adapter: Go

CMD_SETUP     := go mod download
CMD_DEV       := go run .
CMD_SEED      := go run . seed
CMD_FMT       := gofmt -w .
# gofmt has no check mode: fail when it errors or lists unformatted files.
CMD_FMT_CHECK := sh -c 'files=$$(gofmt -l .) && test -z "$$files" || { printf "%s\n" "$$files"; exit 1; }'
CMD_LINT      := go vet ./...
CMD_TYPECHECK := go build -o /dev/null ./...
CMD_TEST      := go test ./...
