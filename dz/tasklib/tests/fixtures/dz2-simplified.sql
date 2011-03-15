CREATE TABLE "dz2_project" (
    "id" INTEGER NOT NULL PRIMARY KEY,
    "owner_id" integer NOT NULL,
    "source_code_url" varchar(1000),
    "title" varchar(120) NOT NULL,
    "django_version" varchar(32) NOT NULL,
    "database_type" varchar(32) NOT NULL,
    "base_python_package" varchar(255),
    "django_settings_module" varchar(255) NOT NULL,
    "site_media" text,
    "additional_python_path_dirs" text,
    "db_host" varchar(100),
    "db_name" varchar(30),
    "db_username" varchar(30),
    "db_password" varchar(30)
)
;
CREATE TABLE "dz2_virtualhostname" (
    "id" INTEGER NOT NULL PRIMARY KEY,
    "project_id" integer NOT NULL,
    "hostname" varchar(253) NOT NULL UNIQUE
)
;
CREATE TABLE "dz2_appbundle" (
    "id" INTEGER NOT NULL PRIMARY KEY,
    "project_id" integer NOT NULL, -- REFERENCES "dz2_project" ("id") DEFERRABLE INITIALLY DEFERRED,
    "bundle_name" varchar(255) NOT NULL,
    "code_revision" varchar(255),
    "creation_date" timestamp with time zone NOT NULL
)
;

CREATE TABLE "dz2_job" (
    "id" INTEGER NOT NULL PRIMARY KEY,
    "task_id" varchar(32),
    "jobcode" varchar(32) NOT NULL,
    "owner_id" integer NOT NULL, -- REFERENCES "djangozoom_team" ("id") DEFERRABLE INITIALLY DEFERRED,
    "issued_by_id" integer NOT NULL, -- REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED,
    "issued_at" timestamp with time zone NOT NULL,
    "project_id" integer -- REFERENCES "dz2_project" ("id") DEFERRABLE INITIALLY DEFERRED
)
;
CREATE TABLE "dz2_log" (
    "id" INTEGER NOT NULL PRIMARY KEY,
    "job_id" integer NOT NULL, -- REFERENCES "dz2_job" ("id") DEFERRABLE INITIALLY DEFERRED,
    "timestamp" timestamp with time zone NOT NULL,
    "message" text,
    "logtype" varchar(2) NOT NULL
)
;

CREATE TABLE "dz2_appserverdeployment" (
    "id" INTEGER NOT NULL PRIMARY KEY,
    "project_id" integer NOT NULL, -- REFERENCES "dz2_project" ("id") DEFERRABLE INITIALLY DEFERRED,
    "bundle_id" integer NOT NULL, -- REFERENCES "dz2_appbundle" ("id") DEFERRABLE INITIALLY DEFERRED,
    "server_ip" inet NOT NULL,
    "server_port" integer CHECK ("server_port" >= 0) NOT NULL,
    "server_instance_id" varchar(32) NOT NULL,
    "creation_date" timestamp with time zone NOT NULL,
    "deactivation_date" timestamp with time zone
)
;

CREATE TABLE "dz2_configguess" (
    "id" integer NOT NULL PRIMARY KEY,
    "project_id" integer NOT NULL REFERENCES "dz2_project" ("id"),
    "field" varchar(100) NOT NULL,
    "value" varchar(1000) NOT NULL,
    "is_primary" bool NOT NULL,
    "basis" varchar(50)
)
;
