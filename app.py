# app.py
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON
from datetime import datetime
import os
import subprocess

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_secret_key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', '')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Server(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    domain = db.Column(db.String(255), nullable=False)
    ssl_enabled = db.Column(db.Boolean, default=True)
    ssl_cert_path = db.Column(db.String(255))
    ssl_key_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    routes = db.relationship('Route', backref='server', lazy=True, cascade="all, delete-orphan")

class Route(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_id = db.Column(db.Integer, db.ForeignKey('server.id'), nullable=False)
    path = db.Column(db.String(255), nullable=False)
    target_domain = db.Column(db.String(255), nullable=False)
    use_rewrite = db.Column(db.Boolean, default=True)
    additional_config = db.Column(JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def generate_nginx_config(server):
    """Generate Nginx configuration for a server based on its routes"""
    config = []
    
    # HTTP server block for SSL redirect
    if server.ssl_enabled:
        config.append(f"""
# {server.name} - HTTP server block to redirect all traffic to HTTPS
server {{
    listen 80;
    server_name {server.domain};
    # Redirect HTTP to HTTPS
    return 301 https://$host$request_uri;
}}
""")

    # HTTPS server block
    config.append(f"""
# {server.name} - {'HTTPS' if server.ssl_enabled else 'HTTP'} server block
server {{
    listen {443 if server.ssl_enabled else 80}{"" if not server.ssl_enabled else " ssl"};
    server_name {server.domain};""")
    
    # SSL certificates if enabled
    if server.ssl_enabled:
        config.append(f"""
    # SSL certificates
    ssl_certificate {server.ssl_cert_path};
    ssl_certificate_key {server.ssl_key_path};
    # Modern SSL settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;""")

    config.append("""
    # Disable IPv6 for upstream connections
    resolver 8.8.8.8 ipv6=off;
    """)
    
    # Add routes
    for route in server.routes:
        if route.use_rewrite:
            rewrite_rule = f"    rewrite ^{route.path}(.*)$ $1 break;"
        else:
            rewrite_rule = ""
        
        additional_config = ""
        if route.additional_config:
            for key, value in route.additional_config.items():
                additional_config += f"        {key} {value};\n"
        
        config.append(f"""
    location {route.path} {{
{rewrite_rule}
        proxy_pass https://{route.target_domain};
        proxy_set_header Host {route.target_domain};
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # SSL settings for upstream
        proxy_ssl_protocols TLSv1.2 TLSv1.3;
        proxy_ssl_server_name on; # Enable SNI
        proxy_ssl_verify off; # Temporarily disable SSL verification for debugging
{additional_config}
    }}""")
    
    # Default location
    config.append("""
    # Optional: Default location for unmatched routes
    location / {
        return 404 "Route not found";
    }""")
    
    # Logging settings
    config.append(f"""
    # Logging settings
    access_log /var/log/nginx/nginx-manager/{server.domain}.access.log;
    error_log /var/log/nginx/nginx-manager/{server.domain}.error.log;
}}
""")
    
    return "".join(config)

def deploy_configuration(server):
    """Deploy the configuration for a server to Nginx"""
    config_content = generate_nginx_config(server)
    config_path = f"/etc/nginx/sites-available/{server.domain}"
    
    # Ensure directory exists
    os.makedirs("/etc/nginx/sites-available", exist_ok=True)
    os.makedirs("/var/log/nginx/nginx-manager", exist_ok=True)
    
    # Write configuration file
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    # Create symbolic link if it doesn't exist
    enabled_path = f"/etc/nginx/sites-enabled/{server.domain}"
    if not os.path.exists(enabled_path):
        os.symlink(config_path, enabled_path)
    
    # Test configuration
    result = subprocess.run(['nginx', '-t'], capture_output=True, text=True)
    if result.returncode != 0:
        # If there's an error, delete the file and symlink
        os.remove(config_path)
        if os.path.exists(enabled_path):
            os.remove(enabled_path)
        return False, result.stderr
    
    # Reload Nginx
    reload_result = subprocess.run(['systemctl', 'reload', 'nginx'], capture_output=True, text=True)
    if reload_result.returncode != 0:
        return False, reload_result.stderr
    
    return True, "Configuration deployed successfully"

@app.route('/')
def index():
    servers = Server.query.all()
    return render_template('index.html', servers=servers)

@app.route('/server/new', methods=['GET', 'POST'])
def new_server():
    if request.method == 'POST':
        name = request.form['name']
        domain = request.form['domain']
        ssl_enabled = 'ssl_enabled' in request.form
        ssl_cert_path = request.form.get('ssl_cert_path', '')
        ssl_key_path = request.form.get('ssl_key_path', '')
        
        # Validation
        if not name or not domain:
            flash('Name and domain are required', 'error')
            return render_template('server_form.html')
            
        if ssl_enabled and (not ssl_cert_path or not ssl_key_path):
            flash('SSL certificate and key paths are required when SSL is enabled', 'error')
            return render_template('server_form.html')
        
        server = Server(
            name=name,
            domain=domain,
            ssl_enabled=ssl_enabled,
            ssl_cert_path=ssl_cert_path,
            ssl_key_path=ssl_key_path
        )
        
        db.session.add(server)
        try:
            db.session.commit()
            flash('Server added successfully', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding server: {str(e)}', 'error')
    
    return render_template('server_form.html')

@app.route('/server/<int:server_id>')
def view_server(server_id):
    server = Server.query.get_or_404(server_id)
    return render_template('server_detail.html', server=server)

@app.route('/server/<int:server_id>/edit', methods=['GET', 'POST'])
def edit_server(server_id):
    server = Server.query.get_or_404(server_id)
    
    if request.method == 'POST':
        server.name = request.form['name']
        server.domain = request.form['domain']
        server.ssl_enabled = 'ssl_enabled' in request.form
        server.ssl_cert_path = request.form.get('ssl_cert_path', '')
        server.ssl_key_path = request.form.get('ssl_key_path', '')
        
        # Validation
        if not server.name or not server.domain:
            flash('Name and domain are required', 'error')
            return render_template('server_form.html', server=server)
            
        if server.ssl_enabled and (not server.ssl_cert_path or not server.ssl_key_path):
            flash('SSL certificate and key paths are required when SSL is enabled', 'error')
            return render_template('server_form.html', server=server)
        
        try:
            db.session.commit()
            flash('Server updated successfully', 'success')
            return redirect(url_for('view_server', server_id=server.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating server: {str(e)}', 'error')
    
    return render_template('server_form.html', server=server)

@app.route('/server/<int:server_id>/delete', methods=['POST'])
def delete_server(server_id):
    server = Server.query.get_or_404(server_id)
    
    try:
        # Remove Nginx configuration files
        config_path = f"/etc/nginx/sites-available/{server.domain}"
        enabled_path = f"/etc/nginx/sites-enabled/{server.domain}"
        
        if os.path.exists(config_path):
            os.remove(config_path)
        if os.path.exists(enabled_path):
            os.remove(enabled_path)
        
        # Delete from database
        db.session.delete(server)
        db.session.commit()
        
        # Reload Nginx
        subprocess.run(['systemctl', 'reload', 'nginx'])
        
        flash('Server deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting server: {str(e)}', 'error')
    
    return redirect(url_for('index'))

@app.route('/server/<int:server_id>/route/new', methods=['GET', 'POST'])
def new_route(server_id):
    server = Server.query.get_or_404(server_id)
    
    if request.method == 'POST':
        path = request.form['path']
        target_domain = request.form['target_domain']
        use_rewrite = 'use_rewrite' in request.form
        
        # Validation
        if not path or not target_domain:
            flash('Path and target domain are required', 'error')
            return render_template('route_form.html', server=server)
        
        # Ensure path starts with /
        if not path.startswith('/'):
            path = '/' + path
        
        route = Route(
            server_id=server.id,
            path=path,
            target_domain=target_domain,
            use_rewrite=use_rewrite,
            additional_config={}
        )
        
        db.session.add(route)
        try:
            db.session.commit()
            flash('Route added successfully', 'success')
            return redirect(url_for('view_server', server_id=server.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding route: {str(e)}', 'error')
    
    return render_template('route_form.html', server=server)

@app.route('/route/<int:route_id>/edit', methods=['GET', 'POST'])
def edit_route(route_id):
    route = Route.query.get_or_404(route_id)
    server = route.server
    
    if request.method == 'POST':
        route.path = request.form['path']
        route.target_domain = request.form['target_domain']
        route.use_rewrite = 'use_rewrite' in request.form
        
        # Validation
        if not route.path or not route.target_domain:
            flash('Path and target domain are required', 'error')
            return render_template('route_form.html', server=server, route=route)
        
        # Ensure path starts with /
        if not route.path.startswith('/'):
            route.path = '/' + route.path
        
        try:
            db.session.commit()
            flash('Route updated successfully', 'success')
            return redirect(url_for('view_server', server_id=server.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating route: {str(e)}', 'error')
    
    return render_template('route_form.html', server=server, route=route)

@app.route('/route/<int:route_id>/delete', methods=['POST'])
def delete_route(route_id):
    route = Route.query.get_or_404(route_id)
    server_id = route.server_id
    
    try:
        db.session.delete(route)
        db.session.commit()
        flash('Route deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting route: {str(e)}', 'error')
    
    return redirect(url_for('view_server', server_id=server_id))

@app.route('/server/<int:server_id>/deploy', methods=['POST'])
def deploy_server(server_id):
    server = Server.query.get_or_404(server_id)
    
    success, message = deploy_configuration(server)
    
    if success:
        flash('Configuration deployed successfully', 'success')
    else:
        flash(f'Error deploying configuration: {message}', 'error')
    
    return redirect(url_for('view_server', server_id=server_id))

@app.route('/server/<int:server_id>/config')
def view_config(server_id):
    server = Server.query.get_or_404(server_id)
    config = generate_nginx_config(server)
    
    return render_template('view_config.html', server=server, config=config)

if __name__ == '__main__':
    # Create tables
    with app.app_context():
        db.create_all()
    
    app.run(debug=True, host='0.0.0.0')