import tkinter as tk
from tkinter import ttk
import os
import logging

logger = logging.getLogger("power_monitor")

class ThemeManager:
    """Manages application themes for the Rack Power Monitor."""
    
    def __init__(self, root):
        """Initialize the theme manager.
        
        Args:
            root: The Tkinter root window
        """
        self.root = root
        self.current_theme = "default"
    
    def apply_theme(self, theme_name):
        """Apply the specified theme to the application.
        
        Args:
            theme_name: The name of the theme to apply ('default' or 'dark')
        """
        self.current_theme = theme_name.lower()
        
        if self.current_theme == "dark":
            self._apply_dark_theme()
        else:
            self._apply_default_theme()
            
        logger.info(f"Applied {theme_name} theme")
        
    def _apply_default_theme(self):
        """Apply the default light theme."""
        style = ttk.Style()
        
        # Reset to default theme
        style.theme_use('default')
        
        # Configure colors
        style.configure(".", 
                      background=self.root.cget('background'),
                      foreground="black",
                      font=("Segoe UI", 10))
        
        # No custom styling needed for default theme
        
    def _apply_dark_theme(self):
        """Apply the dark theme."""
        style = ttk.Style()
        
        # Start with default theme as base
        style.theme_use('default')
        
        # Define colors
        bg_color = "#1e1e1e"
        fg_color = "#d4d4d4" 
        accent_color = "#007acc"
        button_bg = "#3c3c3c"
        entry_bg = "#2d2d2d"
        border_color = "#555555"
        
        # Configure root
        self.root.configure(background=bg_color)
        
        # Configure base style
        style.configure(".", 
                      background=bg_color,
                      foreground=fg_color,
                      fieldbackground=entry_bg,
                      troughcolor=entry_bg,
                      font=("Segoe UI", 10))
        
        # Configure TButton
        style.configure("TButton", 
                      background=button_bg,
                      foreground=fg_color,
                      bordercolor=border_color,
                      focuscolor=accent_color)
        style.map("TButton",
                background=[('active', '#505050'), ('pressed', '#0e639c')],
                foreground=[('active', fg_color), ('pressed', '#ffffff')])
                
        # Configure TFrame
        style.configure("TFrame", background=bg_color)
                
        # Configure TLabel
        style.configure("TLabel", background=bg_color, foreground=fg_color)
                
        # Configure TEntry
        style.configure("TEntry", 
                      fieldbackground=entry_bg,
                      foreground=fg_color,
                      bordercolor=border_color)
        
        # Configure TNotebook
        style.configure("TNotebook", background=bg_color, tabmargins=[2, 5, 2, 0])
        style.configure("TNotebook.Tab", 
                      background="#252526",
                      foreground=fg_color,
                      padding=[10, 2],
                      bordercolor=bg_color)
        style.map("TNotebook.Tab",
                background=[('selected', bg_color)],
                expand=[('selected', [1, 1, 1, 0])])
                
        # Configure Treeview
        style.configure("Treeview", 
                      background=entry_bg,
                      foreground=fg_color,
                      fieldbackground=entry_bg)
        style.map("Treeview",
                background=[('selected', '#094771')],
                foreground=[('selected', '#ffffff')])
                
        # Configure TCheckbutton
        style.configure("TCheckbutton", 
                      background=bg_color,
                      foreground=fg_color)
        
        # Configure TRadiobutton
        style.configure("TRadiobutton", 
                      background=bg_color,
                      foreground=fg_color)
                      
        # Configure TProgressbar
        style.configure("Horizontal.TProgressbar", 
                      background=accent_color,
                      troughcolor=entry_bg)
                      
        # Configure TLabelframe
        style.configure("TLabelframe", 
                      background=bg_color,
                      foreground=fg_color,
                      bordercolor=border_color)
        style.configure("TLabelframe.Label", 
                      background=bg_color,
                      foreground=fg_color)
                      
        # Configure TScrollbar
        style.configure("TScrollbar", 
                      background=button_bg,
                      troughcolor=entry_bg,
                      bordercolor=border_color,
                      arrowcolor=fg_color)
                      
        # Configure TPanedwindow
        style.configure("TPanedwindow", 
                      background=bg_color)
                      
class PowerMonitorApp:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.theme_manager = ThemeManager(root)
        theme = self.config.get('ui_theme', 'Default')
        self.theme_manager.apply_theme(theme)
    
    def _apply_theme_changes(self):
        """Apply theme changes to the application."""
        # Apply chart theme (will take effect on next chart creation)
        
        # Apply UI theme if implemented
        ui_theme = self.ui_theme_var.get()
        self.app.theme_manager.apply_theme(ui_theme)