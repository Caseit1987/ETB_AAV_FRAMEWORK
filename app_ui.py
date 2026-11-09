import tkinter as tk
from tkinter import ttk, messagebox
import requests

API_URL = "http://localhost:8000/api/assessments"

class RooTXChassisDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("RooTX Architectural Command Center")
        self.root.geometry("800x400")
        header = tk.Label(root, text="RooTX Vulnerability & Staffing Alignment Board", font=("Arial", 16, "bold"), pady=10)
        header.pack()
        self.tree = ttk.Treeview(root, columns=("ID", "Project", "Status", "Assigned", "Updated"), show="headings")
        self.tree.heading("ID", text="Assessment ID")
        self.tree.heading("Project", text="Project Name")
        self.tree.heading("Status", text="Status")
        self.tree.heading("Assigned", text="Assigned Member")
        self.tree.heading("Updated", text="Last Updated")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        btn_frame = tk.Frame(root)
        btn_frame.pack(fill=tk.X, padx=20, pady=10)
        sync_btn = tk.Button(btn_frame, text="Synchronize Live Feed", font=("Arial", 10, "bold"), command=self.hydrate_dashboard_view)
        sync_btn.pack(side=tk.RIGHT)
        self.hydrate_dashboard_view()

    def hydrate_dashboard_view(self):
        try:
            for item in self.tree.get_children():
                self.tree.delete(item)
            response = requests.get(API_URL, timeout=5)
            if response.status_code == 200:
                for row in response.json():
                    self.tree.insert("", tk.END, values=(row.get("assessment_id"), row.get("project_name"), row.get("status"), row.get("assigned_member_id"), row.get("last_updated")[:19].replace("T", " ")))
            else:
                messagebox.showerror("Sync Exception", f"Backend rejected lookup: {response.status_code}")
        except requests.exceptions.RequestException as err:
            messagebox.showerror("Pipeline Disconnect", f"Could not map incoming data fields: {str(err)}")

if __name__ == "__main__":
    window = tk.Tk()
    app = RooTXChassisDashboard(window)
    window.mainloop()
