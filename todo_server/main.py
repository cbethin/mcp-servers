from server import mcp

if __name__ == "__main__":
    # The todos resources and tools are already registered in server.py
    print("Starting Todo Server...")
    try:
        mcp.run()
    except Exception as e:
        print(f"Error starting Todo Server: {e}")