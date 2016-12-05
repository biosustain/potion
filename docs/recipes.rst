
Advanced Recipes
================


HistoryMixin
-------------

This mixin keeps a simple history of changes that have been made to a resource, storing them in a database table with a JSON field.
:class:`HistoryMixin` is a drop-in addition to any :class:`ModelResource`.

.. code-block:: python


    ChangeSet = fields.Object({
        "updated_at": fields.DateTime(),
        "changes": fields.List(fields.Object({
            "attribute": fields.String(),
            "old": fields.Any(nullable=True),
            "new": fields.Any(nullable=True)
        }))
    })


    class HistoryRecord(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        object_type = db.Column(db.String(20), index=True, nullable=False)
        object_id = db.Column(db.Integer, index=True, nullable=False)
        updated_at = db.Column(db.DateTime, default=func.now(), nullable=False)
        changes = db.Column(postgresql.JSONB)

        __mapper_args__ = {
            "order_by": "updated_at"
        }


    class HistoryMixin(object):
        @ItemRoute.GET('/history', rel="history")
        def history(self, item) -> fields.List(ChangeSet):
            history = HistoryRecord.query \
                .filter_by(object_type=self.meta.model.__tablename__,
                           object_id=getattr(item, self.meta.get('id_attribute', 'id'))) \
                .all()

            return history


    @before_update.connect_via(ANY, weak=False)
    def history_on_update(resource, item, changes):
        if issubclass(resource, HistoryMixin):
            history = HistoryRecord(object_type=item.__tablename__,
                                    object_id=getattr(item, resource.meta.get('id_attribute', 'id')),
                                    changes=[])

            fields_by_attribute = {
                field.attribute or key: field for key, field in resource.schema.fields.items()
            }

            for attribute, change in changes.items():
                field = fields_by_attribute[attribute]
                history.changes.append({
                    "attribute": attribute,
                    "old": field.output(attribute, item),
                    "new": field.output(attribute, changes)
                })

            db.session.add(history)


ArchivingResource
-----------------

Sometimes soft-deletion is preferable over full deletion. This custom :class:`ModelResource` and :class:`Manager` does
not delete items, instead it *archives* them, removing them from the main instances route. Archived items can be viewed
in the archive route from where they can be restored but not updated.

Replace :class:`RelationalManager` with an appropriate base class, such as :class:`SQLAlchemyManager`. :class:`PrincipalManager` can also be used as the base class for the manager with
some minor changes.

.. code-block:: python

    class Location(Enum):
        ARCHIVE_ONLY = 1
        INSTANCES_ONLY = 2
        BOTH = 3
    
    
    class ArchiveManager(RelationalManager):
        def _query(self, source=Location.INSTANCES_ONLY):
            query = super()._query(self)
    
            if source == Location.BOTH:
                return query
            elif source == Location.ARCHIVE_ONLY:
                return query.filter(getattr(self.model, 'is_archived') == True)
            else:
                return query.filter(getattr(self.model, 'is_archived') == False)
    
        def instances(self, where=None, sort=None, source=Location.INSTANCES_ONLY):
            query = self._query(source)
            if where:
                expressions = [self._expression_for_condition(condition) for condition in where]
                query = self._query_filter(query, self._and_expression(expressions))
            if sort:
                query = self._query_order_by(query, sort)
            return query
    
        def archive_instances(self, page, per_page, where=None, sort=None):
            return self\
                .instances(where=where, sort=sort, source=Location.ARCHIVE_ONLY)\
                .paginate(page=page, per_page=per_page)
    
        def read(self, id, source=Location.INSTANCES_ONLY):
            query = self._query(source)
            if query is None:
                raise ItemNotFound(self.resource, id=id)
            return self._query_filter_by_id(query, id)


    class ArchivingResource(ModelResource):
        class Meta:
            manager = ArchiveManager
            exclude_routes = ['destroy'] # we're using rel="archive" instead.

        class Schema:
            is_archived = fields.Boolean(io='r')

        @Route.GET('/<int:id>', rel="self", attribute="instance")
        def read(self, id) -> fields.Inline('self'):
            return self.manager.read(id, source=Location.BOTH)
    
        @read.PATCH(rel="update")
        def update(self, properties, id):
            item = self.manager.read(id, source=Location.INSTANCES_ONLY)
            updated_item = self.manager.update(item, properties)
            return updated_item
    
        update.response_schema = update.request_schema = fields.Inline('self', patch_instance=True)
    
        @update.DELETE(rel="archive")
        def destroy(self, id):
            item = self.manager.read(id, source=Location.INSTANCES_ONLY)
            self.manager.update(item, {"is_archived": True})
            return None, 204
    
        @Route.GET("/archive")
        def archive_instances(self, **kwargs):
            return self.manager.archive_instances(**kwargs)
    
        archive_instances.request_schema = archive_instances.response_schema = Instances()
    
        @Route.GET('/archive/<int:id>', rel="readArchived")
        def read_archive(self, id) -> fields.Inline('self'):
            item = self.manager.read(id, source=Location.ARCHIVE_ONLY)
    
        @Route.POST('/archive/<int:id>/restore', rel="restoreFromArchive")
        def restore_from_archive(self, id) -> fields.Inline('self'):
            item = self.manager.read(id, source=Location.ARCHIVE_ONLY)
            return self.manager.update(item, {"is_archived": False})

