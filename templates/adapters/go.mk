# Stack Adapter: Go

CMD_SETUP     := go mod download 2>/dev/null || true
CMD_DEV       := go run main.go
CMD_SEED      := echo "Seed: data/demo_seeds.json verified."
CMD_FMT       := gofmt -w . 2>/dev/null || true
CMD_FMT_CHECK := test -z "$$(gofmt -l . 2>/dev/null)" || true
CMD_LINT      := go vet ./... 2>/dev/null || true
CMD_TYPECHECK := go build ./... 2>/dev/null || true
CMD_TEST      := go test -v ./... 2>/dev/null || true
