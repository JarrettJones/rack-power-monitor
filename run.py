"""
Main entry point for Rack Power Monitor application
"""
import os
import sys
import importlib

# Set up proper paths
base_dir = os.path.dirname(os.path.abspath(__file__))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)

# Dynamically import and run the main module
if __name__ == "__main__":
    try:
        # Import the module
        if getattr(sys, 'frozen', False):
            # When packaged, use the bundled path
            from rack_power_monitor.gui import main_window
        else:
            # In development, use the src path
            from src.rack_power_monitor.gui import main_window
            
        # Run the application
        main_window.main()
    except Exception as e:
        import traceback
        print(f"Error starting application: {e}")
        print("Traceback:")
        traceback.print_exc()
        
        # Show error in GUI if possible
        try:
            import tkinter.messagebox as mb
            mb.showerror("Error", f"Failed to start: {str(e)}")
        except:
            pass
            
        # Keep console window open if there was an error
        if not getattr(sys, 'frozen', False):
            input("Press Enter to exit...")