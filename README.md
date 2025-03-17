# ProxyMoxy 🚀

ProxyMoxy is a simple tool to map single domain endpoints to domains using Nginx. It acts as a dynamic reverse proxy manager, allowing you to create, edit, and deploy routing rules with ease.

## Example: How It Works ⚡

Imagine you have a frontend at `example.com` and an API running at `api.example.com`. With ProxyMoxy, you can route `example.com/api` to `api.example.com` seamlessly:

1. **Define a Server** → `example.com`
2. **Add a Route** → `/api` → `api.example.com`
3. **Deploy** → Requests to `example.com/api` now go to `api.example.com` 🎉

## Quick Setup 🛠️

### Prerequisites

- **Linux Server** with `Nginx` installed
- **Python 3.7+**
- **PostgreSQL** (for storing configurations)
- **SSL Certificates** (if using HTTPS)

### Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/abdulsaheel/proxymoxy.git
   cd proxymoxy
   ```
2. Set up a virtual environment (optional but recommended):
   ```sh
   python3 -m venv venv
   source venv/bin/activate 
   ```
3. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
4. Set up environment variables:
   ```sh
   export SECRET_KEY='your_secret_key'
   export DATABASE_URL='postgresql://username:password@host/dbname'
   ```
5. Initialize the database:
   ```sh
   flask db upgrade
   ```
6. Run the application:
   ```sh
   python app.py
   ```
   Access the web UI at `http://localhost:5000`.

## Usage 🚀

### 1. Adding a Server

- Go to `http://localhost:5000/server/new`.
- Enter a domain and optional SSL settings.

### 2. Adding Routes

- Open the server details page.
- Define paths (e.g., `/api`) and target domains (e.g., `backend.example.com`).

### 3. Deploying to Nginx

- Click "Deploy" to apply the configuration.
- ProxyMoxy writes files to `/etc/nginx/sites-available/` and enables them.

If needed, reload Nginx manually:

```sh
sudo systemctl reload nginx
```

## Logs & Debugging 🐛

- Nginx access logs: `/var/log/nginx/proxymoxy/{domain}.access.log`
- Nginx error logs: `/var/log/nginx/proxymoxy/{domain}.error.log`
- App logs: `flask logs` or `journalctl -u flask-app`

## Contributing 🤝

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature-name`).
3. Commit your changes (`git commit -m 'Add feature'`).
4. Push the branch (`git push origin feature-name`).
5. Open a Pull Request.

## License 📜

This project is licensed under the MIT License.

## Author ✨

Developed by [abdulsaheel](https://github.com/abdulsaheel).
