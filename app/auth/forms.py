from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, Email, Length, ValidationError

from lib.models import ActivationCode, User


class SignUpForm(FlaskForm):
  # pylint: disable=no-self-argument

  first_name = StringField("First Name", validators=[DataRequired(), Length(min=1, max=50)])
  last_name = StringField("Last Name", validators=[DataRequired(), Length(min=1, max=50)])
  email = StringField("Email", validators=[DataRequired(), Email(), Length(min=1, max=255)])
  username = StringField("Username", validators=[DataRequired(), Length(min=1, max=50)])
  activation_code = StringField("Activation Code", validators=[DataRequired()])
  password = StringField("Password", validators=[DataRequired(), Length(min=10)])

  def validate_email(form, email):
    if User.query.filter_by(email=email.data).count() > 0:
      raise ValidationError("Email already in use")

  def validate_username(form, username):
    if User.query.filter_by(username=username.data).count() > 0:
      raise ValidationError("Username already in use")

  def validate_activation_code(form, ac):
    ac = ac.data
    if ActivationCode.query.filter_by(id=ac).count() == 0:
      raise ValidationError("Invalid activation code")
    num_uses = User.query.filter_by(activation_code=ac).count()
    if num_uses > 0:
      raise ValidationError("Validation code already used")
