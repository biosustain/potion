from blinker import ANY
from flask import Flask
from flask_login import LoginManager, current_user, login_required, UserMixin
from flask_sqlalchemy import SQLAlchemy
from flask_principal import Principal, Identity, UserNeed, AnonymousIdentity, identity_loaded, RoleNeed
from sqlalchemy.orm import relationship

from flask_potion.contrib.alchemy import SQLAlchemyManager
from flask_potion import fields, signals, Api, ModelResource
from flask_potion.contrib.principals import principals


app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'

db = SQLAlchemy(app)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(), nullable=False)
    is_admin = db.Column(db.Boolean(), default=False)
    is_editor = db.Column(db.Boolean(), default=False)


class Article(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    author = relationship(User)
    content = db.Column(db.Text)


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey(Article.id), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    article = relationship(Article)
    author = relationship(User)
    message = db.Column(db.Text)


login_manager = LoginManager(app)


@login_manager.request_loader
def load_user_from_request(request):
    if request.authorization:
        username, password = request.authorization.username, request.authorization.password

        # XXX replace this with an actual password check.
        if username == password:
            return User.query.filter_by(username=username).first()
    return None


principals = Principal(app)

@principals.identity_loader
def read_identity_from_flask_login():
    if current_user.is_authenticated():
        return Identity(current_user.id)
    return AnonymousIdentity()


@identity_loaded.connect_via(app)
def on_identity_loaded(sender, identity):

    if not isinstance(identity, AnonymousIdentity):
        identity.provides.add(UserNeed(identity.id))

        if current_user.is_editor:
            identity.provides.add(RoleNeed('editor'))

        if current_user.is_admin:
            identity.provides.add(RoleNeed('admin'))


api = Api(app,
          decorators=[login_required],
          default_manager=principals(SQLAlchemyManager))


class UserResource(ModelResource):
    class Meta:
        model = User


class ArticleResource(ModelResource):
    class Schema:
        author = fields.ToOne('user')

    class Meta:
        model = Article
        read_only_fields = ['author']
        permissions = {
            'create': 'editor',
            'update': ['user:author', 'admin']
        }


class CommentResource(ModelResource):
    class Schema:
        article = fields.ToOne('article')
        author = fields.ToOne('user')

    class Meta:
        model = Comment
        read_only_fields = ['author']
        permissions = {
            'create': 'anybody',
            'update': 'user:author',
            'delete': ['update:article', 'admin']
        }


for resource in (UserResource, ArticleResource, CommentResource):
    api.add_resource(resource)


@signals.before_create.connect_via(ANY)
def before_create_article_comment(sender, item):
    if issubclass(sender, (ArticleResource, CommentResource)):
        item.author_id = current_user.id

db.create_all()

if __name__ == '__main__':
    # Add some example users
    db.session.add(User(username='editorA', is_editor=True))
    db.session.add(User(username='editorB', is_editor=True))
    db.session.add(User(username='admin', is_admin=True))
    db.session.add(User(username='user'))
    db.session.commit()

    app.run()