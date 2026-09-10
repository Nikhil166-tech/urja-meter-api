import argparse
import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Urja Meter Ops Clean API Service")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    print(f"⚡ Starting Urja Meter Ops API Service on http://{args.host}:{args.port}")
    print(f"📚 Interactive Swagger UI: http://localhost:{args.port}/docs")
    print(f"📖 Scalar API Reference: http://localhost:{args.port}/scalar")
    print(f"🗺️ Web Client Dashboard: http://localhost:{args.port}/dashboard")
    uvicorn.run("urja_api.main:app", host=args.host, port=args.port, reload=args.reload)
