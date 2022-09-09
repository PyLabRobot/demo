import os

import sqlalchemy

from flask import render_template, request,jsonify, Blueprint, current_app, send_file, flash
from flask_login import current_user, login_required
import sqlalchemy
from werkzeug.utils import secure_filename

from app import dbs
from lib.models import File, Project

platform = Blueprint("platform", __name__, url_prefix="/platform", template_folder="templates", static_folder="static")


@platform.route("/")
@login_required
def index():
  return render_template("platform/index.html")


@platform.route("/projects", methods=["POST"])
@login_required
def create_project():
  name = request.json.get("name")
  project = Project(name=name, owner_id=current_user.id)

  try:
    dbs.add(project)
    dbs.commit()
  except Exception as e:
    dbs.rollback()
    current_app.logger.error(e)
    return jsonify({"error": "Could not create project"}), 500

  return jsonify(project.serialize())


@platform.route("/projects/<id_>", methods=["GET"])
@login_required
def get_project(id_):
  try:
    project = Project.query.get(id_)
  except sqlalchemy.exc.DataError as e:
    current_app.logger.error(e)
    if request.headers.get("Accept") == "application/json":
      return jsonify({"error": "Malformed id"}), 400
    else:
      return render_template("error.html", error_code=400, title="Malformed id"), 500

  if project is None:
    if request.headers.get("Accept") == "application/json":
      return jsonify({"error": "Project not found"}), 404
    else:
      flash("Project not found")
      return render_template("error.html", error_code=404, title="Project not found"), 404

  if request.headers.get("Accept") == "application/json":
    return jsonify(project.serialize())
  else:
    return render_template("platform/project.html", project=project)


ALLOWED_EXTENSIONS = {"txt", "tml", "lay", "ctr", "rck"}
def allowed_file(filename):
  return ("." in filename) and (filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS)


def get_file_path(project_id, filename):
  dirs = os.path.join(current_app.config["UPLOAD_DIR"], str(project_id))
  if not os.path.exists(dirs):
    os.makedirs(dirs)
  path = os.path.join(dirs, secure_filename(filename))
  path = os.path.abspath(path)
  return path

def store_file(file, project_id):
  path = get_file_path(project_id, file.filename)
  file.save(path)
  return path


@platform.route("/files", methods=["POST"])
@login_required
def create_files():
  if "files" not in request.files:
    return jsonify({"error": "No files part"}), 400

  files = request.files.getlist("files")
  project_id = request.form.get("project_id")
  if project_id is None:
    return jsonify({"error": "No project_id"}), 400

  # Make sure all files are valid
  for file in files:
    # If the user does not select a file, the browser submits an
    # empty file without a filename.
    if file.filename == "":
      return jsonify({"error": "No selected file"}), 400
    if not (file and allowed_file(file.filename)):
      return jsonify({"error": "Invalid file type for file: " + file.filename}), 400

  # Then store the files
  file_objects = []
  for file in files:
    f = File(name=file.filename, project_id=project_id)
    path = store_file(file, project_id)
    f.path = path
    try:
      dbs.add(f)
      dbs.commit()
      file_objects.append(f)
    except Exception as e:
      dbs.rollback()
      current_app.logger.error(e)
      return jsonify({"error": str(e)}), 500

  return jsonify({"success": True, "files": [f.serialize() for f in file_objects]}), 201


@platform.route("/files/<id_>", methods=["GET"])
def get_file(id_):
  try:
    file = File.query.get(id_)
  except sqlalchemy.exc.DataError as e:
    current_app.logger.error(e)
    return jsonify({"error": "Malformed id"}), 400
  if file is None:
    return jsonify({"error": "File not found"}), 404
  return jsonify(file.serialize())


@platform.route("/files/<id_>/download", methods=["GET"])
def download_file(id_):
  try:
    file = File.query.get(id_)
  except sqlalchemy.exc.DataError as e:
    current_app.logger.error(e)
    return jsonify({"error": "Malformed id"}), 400
  if file is None:
    return jsonify({"error": "File not found"}), 404
  path = get_file_path(file.project_id, file.name)
  return send_file(path, as_attachment=True)
