from server import mcp

if __name__ == "__main__":
    # The task resources and tools are already registered in server.py
    print("Starting Task Management Server...")
    try:
        mcp.run()
    except Exception as e:
        print(f"Error starting Task Management Server: {e}")