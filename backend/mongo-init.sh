#!/bin/bash
set -e

# Wait for MongoDB to be ready
until mongosh --quiet --eval "db.adminCommand('ping')" > /dev/null 2>&1; do
  echo "Waiting for MongoDB to be ready..."
  sleep 1
done

mongosh <<EOF
use $MONGO_INITDB_DATABASE

// Create user for the database
db.createUser({
  user: '$MONGODB_USER',
  pwd: '$MONGODB_PASSWORD',
  roles: [
    {
      role: 'readWrite',
      db: '$MONGO_INITDB_DATABASE'
    }
  ]
});

// Create collections
db.createCollection('chats');
db.createCollection('places');

// Create indexes
db.chats.createIndex({ "chat_id": 1 }, { unique: true });
db.places.createIndex({ "place_id": 1 }, { unique: true });

EOF
