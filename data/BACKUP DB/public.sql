/*
 Navicat Premium Data Transfer

 Source Server         : PostgreSQL
 Source Server Type    : PostgreSQL
 Source Server Version : 170004 (170004)
 Source Host           : localhost:5432
 Source Catalog        : Scheduler_DB
 Source Schema         : public

 Target Server Type    : PostgreSQL
 Target Server Version : 170004 (170004)
 File Encoding         : 65001

 Date: 06/03/2026 02:54:03
*/


-- ----------------------------
-- Sequence structure for building_distances_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."building_distances_id_seq";
CREATE SEQUENCE "public"."building_distances_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for buildings_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."buildings_id_seq";
CREATE SEQUENCE "public"."buildings_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for candidates_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."candidates_id_seq";
CREATE SEQUENCE "public"."candidates_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for colleges_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."colleges_id_seq";
CREATE SEQUENCE "public"."colleges_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for courses_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."courses_id_seq";
CREATE SEQUENCE "public"."courses_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for curriculum_subjects_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."curriculum_subjects_id_seq";
CREATE SEQUENCE "public"."curriculum_subjects_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for days_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."days_id_seq";
CREATE SEQUENCE "public"."days_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for instructors_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."instructors_id_seq";
CREATE SEQUENCE "public"."instructors_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for rooms_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."rooms_id_seq";
CREATE SEQUENCE "public"."rooms_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for schedules_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."schedules_id_seq";
CREATE SEQUENCE "public"."schedules_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for subjects_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."subjects_id_seq";
CREATE SEQUENCE "public"."subjects_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for swap_requests_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."swap_requests_id_seq";
CREATE SEQUENCE "public"."swap_requests_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for timeslots_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."timeslots_id_seq";
CREATE SEQUENCE "public"."timeslots_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for users_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."users_id_seq";
CREATE SEQUENCE "public"."users_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Table structure for building_distances
-- ----------------------------
DROP TABLE IF EXISTS "public"."building_distances";
CREATE TABLE "public"."building_distances" (
  "id" int4 NOT NULL DEFAULT nextval('building_distances_id_seq'::regclass),
  "from_building_id" int4 NOT NULL,
  "to_building_id" int4 NOT NULL,
  "travel_time_minutes" int4 NOT NULL
)
;

-- ----------------------------
-- Records of building_distances
-- ----------------------------
INSERT INTO "public"."building_distances" VALUES (2, 1, 5, 15);
INSERT INTO "public"."building_distances" VALUES (3, 1, 2, 10);
INSERT INTO "public"."building_distances" VALUES (9, 2, 5, 7);

-- ----------------------------
-- Table structure for buildings
-- ----------------------------
DROP TABLE IF EXISTS "public"."buildings";
CREATE TABLE "public"."buildings" (
  "id" int4 NOT NULL DEFAULT nextval('buildings_id_seq'::regclass),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "code" varchar(20) COLLATE "pg_catalog"."default",
  "description" text COLLATE "pg_catalog"."default",
  "is_shared" bool NOT NULL DEFAULT false,
  "college_id" int4
)
;

-- ----------------------------
-- Records of buildings
-- ----------------------------
INSERT INTO "public"."buildings" VALUES (5, 'Grand Stand', 'E', 'GS ER', 't', NULL);
INSERT INTO "public"."buildings" VALUES (8, 'FIELD', 'FIELD', 'FIELD', 't', NULL);
INSERT INTO "public"."buildings" VALUES (9, 'GYM', 'GYM', 'GYM', 't', NULL);
INSERT INTO "public"."buildings" VALUES (1, 'CCS Building', 'A', 'Computer Science Building', 'f', 4);
INSERT INTO "public"."buildings" VALUES (6, 'CLAMS Building', 'F', 'CLAMS building', 'f', 6);
INSERT INTO "public"."buildings" VALUES (2, 'COE Building', 'B', 'Engineering Building', 'f', 8);
INSERT INTO "public"."buildings" VALUES (10, 'Inner Quad', 'IQ', 'INNER QUAD', 'f', NULL);

-- ----------------------------
-- Table structure for candidates
-- ----------------------------
DROP TABLE IF EXISTS "public"."candidates";
CREATE TABLE "public"."candidates" (
  "id" int4 NOT NULL DEFAULT nextval('candidates_id_seq'::regclass),
  "course_id" int4 NOT NULL,
  "room_id" int4 NOT NULL,
  "timeslot_id" int4 NOT NULL,
  "semester" int4 NOT NULL,
  "year" int4 NOT NULL
)
;

-- ----------------------------
-- Records of candidates
-- ----------------------------

-- ----------------------------
-- Table structure for colleges
-- ----------------------------
DROP TABLE IF EXISTS "public"."colleges";
CREATE TABLE "public"."colleges" (
  "id" int4 NOT NULL DEFAULT nextval('colleges_id_seq'::regclass),
  "code" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default" NOT NULL
)
;

-- ----------------------------
-- Records of colleges
-- ----------------------------
INSERT INTO "public"."colleges" VALUES (4, 'CCS', 'College of Computing Studies');
INSERT INTO "public"."colleges" VALUES (5, 'CBA', 'College of Business Administration');
INSERT INTO "public"."colleges" VALUES (6, 'CLAMS', 'College of Liberal Arts and Mathematics and Science');
INSERT INTO "public"."colleges" VALUES (8, 'COE', 'College of Engineering');

-- ----------------------------
-- Table structure for courses
-- ----------------------------
DROP TABLE IF EXISTS "public"."courses";
CREATE TABLE "public"."courses" (
  "id" int4 NOT NULL DEFAULT nextval('courses_id_seq'::regclass),
  "code" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default" NOT NULL,
  "college_id" int4 NOT NULL
)
;

-- ----------------------------
-- Records of courses
-- ----------------------------
INSERT INTO "public"."courses" VALUES (3, 'BSIS', 'BS Information Systems', 4);
INSERT INTO "public"."courses" VALUES (4, 'BSCS', 'BS Computer Science', 4);
INSERT INTO "public"."courses" VALUES (1, 'BSIT', 'BS Information Technology', 4);
INSERT INTO "public"."courses" VALUES (5, 'HM', 'Hospitality Management', 5);
INSERT INTO "public"."courses" VALUES (6, 'CCE', 'College of Civil Engineering', 8);
INSERT INTO "public"."courses" VALUES (7, 'ComEn', 'Computer Engineer', 8);
INSERT INTO "public"."courses" VALUES (8, 'MM', 'Marketing Management', 5);
INSERT INTO "public"."courses" VALUES (9, 'Polsci', 'Political Science', 6);
INSERT INTO "public"."courses" VALUES (10, 'MB', 'Marine Biology', 6);

-- ----------------------------
-- Table structure for curriculum_subjects
-- ----------------------------
DROP TABLE IF EXISTS "public"."curriculum_subjects";
CREATE TABLE "public"."curriculum_subjects" (
  "id" int4 NOT NULL DEFAULT nextval('curriculum_subjects_id_seq'::regclass),
  "course_id" int4 NOT NULL,
  "year_level" int4 NOT NULL,
  "semester" int4 NOT NULL,
  "code" varchar(50) COLLATE "pg_catalog"."default",
  "description" text COLLATE "pg_catalog"."default",
  "units" varchar(20) COLLATE "pg_catalog"."default",
  "prerequisite" text COLLATE "pg_catalog"."default",
  "is_exit_point" bool DEFAULT false,
  "metadata" text COLLATE "pg_catalog"."default",
  "lec_units" int4 DEFAULT 0,
  "lab_units" int4 DEFAULT 0,
  "extra_info" text COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Records of curriculum_subjects
-- ----------------------------
INSERT INTO "public"."curriculum_subjects" VALUES (1, 3, 1, 1, 'GE – MM', 'Mathematics in the Modern World', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (2, 3, 1, 2, 'GE – AA', 'Art Appreciation', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (3, 3, 1, 1, 'GE – PC', 'Purposive Communication', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (4, 3, 1, 2, 'GE – PH', 'Readings in Philippine History', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (5, 3, 1, 1, 'FIL1', 'Kontekstwalisadong Komunikasyon sa Filipino', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (6, 3, 1, 2, 'RIZAL', 'Rizal’s Life & Works', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (7, 3, 1, 1, 'GEE – RVA', 'Reading Visual Art', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (8, 3, 1, 2, 'CC 103', 'Intermediate Programming', '3', 'CC 102', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (9, 3, 1, 1, 'CC 101', 'Introduction to Computing', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (10, 3, 1, 2, 'IS 121', 'Fundamentals of Information Systems', '3', 'CC 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (11, 3, 1, 1, 'CC 102', 'Fundamentals of Programming', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (12, 3, 1, 2, 'TE 1', 'Multimedia Systems', '3', 'CC 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (13, 3, 1, 1, 'PE 11', 'Movement Enhancement (ME)', '2', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (14, 3, 1, 2, 'PE 12', 'Fitness Exercise (FE)', '2', 'PE 11', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (15, 3, 1, 1, 'NSTP 1', 'National Service Training Program 1', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (16, 3, 1, 2, 'NSTP 2', 'National Service Training Program 2', '3', 'NSTP 1', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (17, 3, 2, 1, 'GE – ST', 'Science, Technology and Society', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (18, 3, 2, 2, 'GE – E', 'Ethics', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (19, 3, 2, 1, 'GE – US', 'Understanding the Self', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (20, 3, 2, 2, 'GE – CW', 'The Contemporary World', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (21, 3, 2, 1, 'AMR', 'Discrete Mathematics', '3', 'GE-MM, CC 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (22, 3, 2, 2, 'CC 105', 'Information Management', '3', 'CC 102, CC103, CC 104', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (23, 3, 2, 1, 'CC 104', 'Data Structures an Algorithms', '3', 'CC 102, CC 103', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (24, 3, 2, 2, 'TE 3', 'Web Systems and Technologies', '3', 'CC 102, CC 103', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (25, 3, 2, 1, 'TE 2', 'Intro to 2D Animation', '3', 'GEE-RVA, GE- AA, CC 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (26, 3, 2, 2, 'TE 4', 'PC Troubleshooting and Networking', '3', 'CC 101, IS 121', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (27, 3, 2, 1, 'IS 211', 'Quantitative Methods', '3', 'GE-MM', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (28, 3, 2, 2, 'IS 221', 'IT Infrastructure & Network Technologies', '3', 'CC 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (29, 3, 2, 1, 'IS 212', 'Organization & Management Concept', '3', 'IS 121', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (30, 3, 2, 2, 'IS 222', 'Enterprise Architecture', '3', 'IS 121, IS 212', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (31, 3, 2, 1, 'IS 213', 'Financial Management', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (32, 3, 2, 2, 'PROE 1', 'Object-Oriented Programming', '3', 'IS 121, IS 212', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (33, 3, 2, 1, 'FIL2', 'Filipino sa Iba’t Ibang Disiplina', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (34, 3, 2, 2, 'PAN1', 'Sinesosyedad/Pelikulang Panlipunan', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (35, 3, 2, 1, 'PE 21', 'Physical Activities Towards Health & Fitness (PATH-Fit) 1 (Dance, Sports, Outdoor & Adventure Activities)', '2', 'PE 12', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (36, 3, 2, 2, 'PE 22', 'Physical Activities Towards Health & Fitness (PATH-Fit) 2 (Dance, Sports, Outdoor & Adventure Activities)', '2', 'PE 21', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (37, 3, 3, 0, 'EXIT', '2D ANIMATION NC III * : COMPUTER SYSTEMS SERVICING NC II', '0', NULL, 't', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (38, 3, 3, 1, 'CC 106', 'Application Development and Emerging Technologies', '3', 'Must be an Associate in Computer Technology Graduate.', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (39, 3, 3, 2, 'TE 6', 'Platform-based Development', '3', 'TE 5', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (40, 3, 3, 1, 'TE 5', 'Advance Database Systems', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (41, 3, 3, 2, 'IS 321', 'IS Strategy, Management & Acquisition', '3', 'ProE 2, IS 312', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (42, 3, 3, 1, 'IS 311', 'IS Project Management 1', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (43, 3, 3, 2, 'IS 322', 'Professional Issues in Information Systems', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (44, 3, 3, 1, 'IS 312', 'Business Process Management', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (45, 3, 3, 2, 'PROE 4', 'IS Project Management 2', '3', 'IS 312, ProE 2, TE 5, IS 313', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (46, 3, 3, 1, 'IS 313', 'System Analysis & Design', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (47, 3, 3, 2, 'PROE 5', 'IT Security & Management', '3', 'ProE 2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (48, 3, 3, 1, 'PROE 2', 'Enterprise System', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (49, 3, 3, 2, 'PROE 6', 'Methods of Research in Computing', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (50, 3, 3, 0, 'EXIT', 'TOTAL 21 * : PROGRAMMING NC III', '0', NULL, 't', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (51, 3, 4, 1, 'IS 411', 'Evaluation of Business Performance', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (52, 3, 4, 2, 'IS 421', 'Capstone 2', '3', 'Reg. 4th Yr. Level', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (53, 3, 4, 1, 'PROE 7', 'Certification Review, Training and Seminar 1', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (54, 4, 1, 1, 'GE – MM', 'Mathematics in the Modern World', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (55, 4, 1, 2, 'GE – PH', 'Readings in Philippine History', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (56, 4, 1, 1, 'FIL1', 'Kontekstwalisadong Komunikasyon sa Filipino', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (57, 4, 1, 2, 'FIL2', 'Filipino sa Iba’t Ibang Disiplina', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (58, 4, 1, 1, 'CC 101', 'Introduction to Computing', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (59, 4, 1, 2, 'GE – CW', 'The Contemporary World', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (60, 4, 1, 1, 'CC 102', 'Fundamentals of Programming', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (61, 4, 1, 2, 'CC 103', 'Intermediate Programming', '3', 'CC 102', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (62, 4, 1, 1, 'GE – US', 'Understanding the Self', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (63, 4, 1, 2, 'GE – PC', 'Purposive Communication', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (64, 4, 1, 1, 'PE 11', 'Movement Enhancement (ME)', '2', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (65, 4, 1, 2, 'DS 101', 'Discrete Structure 1', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (66, 4, 1, 1, 'NSTP 1', 'National Service Training Program 1', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (67, 4, 1, 2, 'PE 12', 'Fitness Exercise (FE)', '2', 'PE 11', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (68, 4, 2, 1, 'GE – AA', 'Art Appreciation', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (69, 4, 2, 2, 'CC 105', 'Information Management', '3', 'CC 103', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (70, 4, 2, 1, 'CC 104', 'Data Structures & Algorithms', '3', 'CC 103', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (71, 4, 2, 2, 'GE – E', 'Ethics', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (72, 4, 2, 1, 'DS 102', 'Discrete Structure 2', '3', 'DS 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (73, 4, 2, 2, 'RIZAL', 'Rizal’s Life & Works', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (74, 4, 2, 1, 'GE – ST', 'Science, Technology & Society', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (75, 4, 2, 2, 'CS PROF ELECT 2', 'Introduction to Data Science', '3', 'SDF 104', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (76, 4, 2, 1, 'SDF 104', 'Object-Oriented Programming', '3', 'CC 102', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (77, 4, 2, 2, 'ACCT 1', 'Fundamentals of Accounting', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (78, 4, 2, 1, 'PAN 1', 'Sinesosyedad/Pelikulang Panlipunan', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (79, 4, 2, 2, 'CS PROF ELECT 3', 'Web Systems & Technologies', '3', 'CC 102', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (80, 4, 2, 1, 'CS PROF
ELECT 1', 'Digital Design', '3', 'DS 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (81, 4, 2, 2, 'AL 101', 'Algorithms & Complexity', '3', 'SDF 104, CC 104', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (82, 4, 2, 1, 'PE 21', 'Physical Activities Towards Health & Fitness (PATH-Fit) 1 (Dance, Sports, Outdoor & Adventure Activities)', '2', 'PE 12', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (83, 4, 2, 2, 'PE 22', 'Physical Activities Towards Health & Fitness (PATH-Fit) 2 (Dance, Sports, Outdoor & Adventure Activities)', '2', 'PE 21', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (84, 4, 3, 0, 'EXIT', 'PROGRAMMING (JAVA) NC III', '0', NULL, 't', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (85, 4, 3, 1, 'CS ELECT 1 –
GV 101', 'Graphics & Visual Computing', '3', 'CC 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (86, 4, 3, 2, 'SE 1', 'Software Engineering 1', '3', 'CC 105', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (87, 4, 3, 1, 'AR 101', 'Computer Architecture & Organization', '3', 'CC 102, CC 104', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (88, 4, 3, 2, 'RES 1', 'Method of Research in Computing', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (89, 4, 3, 1, 'CS PROF
ELECT 4', 'Digital Image Processing', '3', 'CC 104', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (90, 4, 3, 2, 'CS ELECT 2 –
IS 101', 'Intelligent System (Machine Learning)', '3', 'SDF 104, AL 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (91, 4, 3, 1, 'STAT 1', 'Statistics in Computing', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (92, 4, 3, 2, 'CS PROF ELECT 6', 'Natural Language Processing', '3', 'IS 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (93, 4, 3, 1, 'AL 2', 'Automata Theory & Formal Language', '3', 'SDF104', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (94, 4, 3, 2, 'PL 1', 'Programming Languages', '3', 'CC 104, AL 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (95, 4, 3, 1, 'IAS 1', 'Information Assurance & Security', '2', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (96, 4, 3, 2, 'CS PROF ELECT 7', 'Platform-Based Development', '3', 'CC 103', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (97, 4, 3, 1, 'CC 106', 'Application Development & Emerging Technology', '3', 'CC 104, CC 105', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (98, 4, 3, 2, 'CS PROF ELECT
8', 'PC Troubleshooting & Networking', '3', 'CC 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (99, 4, 3, 1, 'CS PROF
ELECT 5', 'Data Mining', '3', 'CS Prof Elect 2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (100, 4, 3, 2, 'SP 1', 'Social Issues & Professional Practice', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (101, 4, 3, 0, 'EXIT', 'VISUAL GRAPHICS NCIII : COMPUTER SYSTEMS SERVICING NC II', '0', NULL, 't', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (102, 4, 4, 1, 'CS ELECT 3-PD 101', 'Parallel and Distributed Computing', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (103, 4, 4, 2, 'NC 101', 'Network and Communication', '3', 'CC 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (104, 4, 4, 1, 'OS 101', 'Operating Systems', '3', 'CC 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (105, 4, 4, 2, 'TH 102', 'Thesis 2', '3', 'THS 101', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (106, 4, 4, 1, 'SE 2', 'Software Engineering 2', '3', 'SE 1', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (107, 4, 4, 1, 'THS 101', 'Thesis 1', '3', 'Res 1', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (108, 4, 4, 1, 'CS PROF ELECT 9', 'Certification, Review, Training & Seminar', '3', '4th Yr. Standing', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (109, 4, 4, 1, 'CS PROF ELECT 10', 'Android Application Development', '3', 'CC 104', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (110, 1, 1, 1, 'GE -MM', 'Mathematics in the Modern World', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (111, 1, 1, 2, 'GEE -RVA', 'Reading Visual Art', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (112, 1, 1, 1, 'GE -PC', 'Purposive Communication', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (113, 1, 1, 2, 'GE -PH', 'Readings in Philippine History & Studies of Indigenous People', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (114, 1, 1, 1, 'GE-GCP', 'Gender, Conflict and Peace', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (115, 1, 1, 2, 'GE -US', 'Understanding the Self', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (116, 1, 1, 1, 'GE -AA', 'Art Appreciation', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (117, 1, 1, 2, 'GE -RIZAL', 'Rizal’s Life & Works', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (118, 1, 1, 1, 'CC 101', 'Introduction to Computing', '3', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (119, 1, 1, 1, 'CC 102', 'Computer Programming 1', '3', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (120, 1, 1, 1, 'PATHFIT 1', 'Physical Activities Towards Health 1', '2', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (121, 1, 1, 2, 'PATHFIT 2', 'Physical Activities Towards Health 2', '2', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (122, 1, 1, 1, 'NSTP 11', 'National Service Training Program 1', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (123, 1, 1, 2, 'NSTP 12', 'National Service Training Program 2', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (124, 1, 2, 1, 'GE -ST', 'Science, Technology and Society', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (125, 1, 2, 2, 'GE -E', 'Ethics', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (126, 1, 2, 1, 'CC 104', 'Data Structures an Algorithms', '3', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (127, 1, 2, 1, 'IT 102', 'Information Assurance and Security 1', '3', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (128, 1, 2, 1, 'IT 103', 'Fundamentals of Database Systems', '3', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (129, 1, 2, 1, 'IT 104', 'Networking 1', '3', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (130, 1, 2, 1, 'IT 105', 'Social and Professional Issues', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (131, 1, 2, 2, 'IC 2', 'Virtualization and Cloud Platforms', '3', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (132, 1, 2, 1, 'IT 106', 'Discrete Mathematics', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (133, 1, 2, 1, 'IC 1', 'Strategic Project Management in IT', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (134, 1, 2, 1, 'PATHFIT 3', 'Physical Activities Towards Health 3', '2', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (135, 1, 3, 1, 'CC 10 6', 'Application Development and EmergingTechnologies', '3', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (136, 1, 3, 1, 'IC 3', 'Research Methods in Computing', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (137, 1, 3, 1, 'IT 109', 'Quantitative Methods (incl. Modeling & Simulation)', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (138, 1, 3, 1, 'PROF.E 3', 'Integrative Programming Technologies 2', '3', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (139, 1, 3, 1, 'IC 4', 'Multimedia System', '3', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (140, 1, 3, 1, 'IT 110', 'Systems integration and Architecture 1', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (141, 1, 3, 1, 'IT 111', 'Advance Database System', '3', '2', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (142, 1, 3, 1, 'PROF.E 4', 'Platform Technologies 1', '3', '3', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (143, 1, 4, 1, 'IC 9', 'Field Trips and Exposure', '3', '', 'f', NULL, 0, 0, NULL);
INSERT INTO "public"."curriculum_subjects" VALUES (144, 1, 4, 1, 'IC 10', 'Certification, Review, Training & Seminar', '3', '2', 'f', NULL, 0, 0, NULL);

-- ----------------------------
-- Table structure for days
-- ----------------------------
DROP TABLE IF EXISTS "public"."days";
CREATE TABLE "public"."days" (
  "id" int4 NOT NULL DEFAULT nextval('days_id_seq'::regclass),
  "label" varchar(10) COLLATE "pg_catalog"."default" NOT NULL
)
;

-- ----------------------------
-- Records of days
-- ----------------------------
INSERT INTO "public"."days" VALUES (1, 'M');
INSERT INTO "public"."days" VALUES (2, 'T');
INSERT INTO "public"."days" VALUES (3, 'W');
INSERT INTO "public"."days" VALUES (4, 'TH');
INSERT INTO "public"."days" VALUES (5, 'F');
INSERT INTO "public"."days" VALUES (6, 'SAT');
INSERT INTO "public"."days" VALUES (7, 'SUN');

-- ----------------------------
-- Table structure for instructors
-- ----------------------------
DROP TABLE IF EXISTS "public"."instructors";
CREATE TABLE "public"."instructors" (
  "id" int4 NOT NULL DEFAULT nextval('instructors_id_seq'::regclass),
  "first_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "last_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "username" varchar(100) COLLATE "pg_catalog"."default",
  "assignable_courses" text COLLATE "pg_catalog"."default",
  "college_id" int4,
  "middle_name" varchar(100) COLLATE "pg_catalog"."default",
  "employment_type" varchar(20) COLLATE "pg_catalog"."default",
  "designation" varchar(100) COLLATE "pg_catalog"."default",
  "preferred_start_time" varchar(10) COLLATE "pg_catalog"."default",
  "preferred_end_time" varchar(10) COLLATE "pg_catalog"."default",
  "max_units" int4,
  "is_active" bool NOT NULL DEFAULT true
)
;

-- ----------------------------
-- Records of instructors
-- ----------------------------
INSERT INTO "public"."instructors" VALUES (16, 'Lara', 'Gonzales', 'lgonzales', 'GE - ST,IT 102,IT 104,IC 1,PATHFIT 3,IT 103,GE - E,GE - CW,CC 105,IT 104,PATHFIT 4,IC 7', 4, 'J.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (10, 'Alvin', 'Lim', 'alim', 'CC 105,TE  3,PE 22,TE 4,IS 221,IS 222,ProE 1,PE 12,PAN 1,CS PROF ELECT 4,PROF.E 2,IC 3', 4, 'D.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (11, 'Renz', 'Manalo', 'rmanalo', 'PAN1,CC 106,IS 313,TE 5,ProE 2,IS 311,IS 312,SDF 104', 4, 'E.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (12, 'Kate', 'Ramos', 'kramos', 'ProE 3,IS 321,IS 322,ProE 5,ProE 4,ProE 6,IS 411,IS 412,ProE 7,IS 421', 4, 'F.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (13, 'Allen', 'Pascual', 'apascual', 'GE - MM,GE - PC,GE - GCP,CC 101,CC 102,PATHFIT 1,GE - AA,NSTP 1,GE - RVA', 4, 'G.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (15, 'Jenny', 'Flores', 'jflores', 'Prof.E 2,PATHFIT 4,IC 2,IT 107,IT 108,Prof.E 1,CC 106,IC 3', 4, 'I.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (17, 'Erika', 'Alcantara', 'ealcantara', 'IT 109,IT 111,Prof.4 E,IC 4,IT 110,IC 5,IC 6,IT 113,ProE 5', 4, 'K.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (18, 'Jasmine', 'Castillo', 'jcastillo', 'CAP 1,IT 114,ProE 7,IC 7,Prof.E 8,CAP 2,IC 10,IC 9,IT PRC,SE 2', 4, 'L.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (21, 'Anthony', 'Valdez', 'avaldez', 'PE 11,Acct 1,CS Prof Elect 3,ACCT 1,IS 322,IS 411,GE - GCP,IT 111,CAP 1', 4, 'O.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (22, 'Faith', 'Soriano', 'fsoriano', 'CS PROF ELECT 10,IAS 1,CC 106,CS PROF ELECT 1,AR 101,IAS 1', 4, 'P.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (23, 'Benedict', 'Sarte', 'bsarte', 'CS PROF ELECT 5,CS Prof Elect 7,CS Prof Elect 8,SP 1,AL 2,IS 221,PROE 3', 4, 'Q.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (24, 'Fabian', 'Ordoñez', 'fordoez', 'IT 109,CS ELECT 1 - GV 101,RES 1,CS ELECT 2 - IS 101,TE 4,PAN1,IS 412', 4, 'R.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (25, 'Harold', 'Cañete', 'hcaete', 'RES 1,RIZAL,CS PROF ELECT 3,TE 2,IS 313,IT 101,PATHFIT 2,IC 2,IT 109,IT 110', 4, 'S.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (26, 'Giselle', 'Panganiban', 'gpanganiban', 'TE 5,CS PROF ELECT 5,CS PROF ELECT 9,IS 311,GE - RVA,IT 108,IC 5,IT 114', 4, 'T.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (28, 'Nathaniel', 'Estrella', 'nestrella', 'IT 107,STAT 1,PL 1,CS ELECT 3-PD 101,IS 312,PROF.4 E,IC 6', 4, 'V.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (1, 'Juan', 'Dela Cruz', NULL, 'AL 101,PE 22,CS Elect 1 - GV 101,AR 101,CS Prof Elect 4,Stat 1,AL 2', 4, NULL, 'regular', 'Dean', NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (2, 'Maria', 'Santos', 'msantos', 'PAN 1,CS Prof Elect 1,PE 21,CC 105,GE - E,RIZAL,CS Prof Elect 2', 4, NULL, 'regular', 'Director', NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (3, 'John', 'Doe', 'jdoe', 'CC 103,GE - PC,DS 101,PE 12,GE - AA,CC 104,DS 102,GE - ST,SDF 104', 4, NULL, 'regular', 'Associate Dean', NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (4, 'Feliz', 'Dad', 'fdad', 'GE - MM,FIL1,CC 101,CC 102,GE - US,PE 11,GE - PH,FIL2,GE - CW,SP 1', 4, 'Navi', 'regular', 'Program Chair', NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (14, 'Kim', 'Navarro', 'knavarro', 'GE - PH,GE -RIZAL,IT 101,CC 103,PATHFIT 2,NSTP 2,GE - US,CC 104,IT 106,AMR,IS 213', 4, 'H.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (27, 'Joaquin', 'Velasco', 'jvelasco', 'CS ELECT 1 - GV 101,Prof.3 E,IS 211,IS 212,NSTP 1,IT 103,PROF.E 8,IT PRC', 4, 'U.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (5, 'John', 'Cruz', 'jcruz', 'CS Prof Elect 5,SE 1,Res 1,CS Elect 2 - IS 101,CS Prof Elect 6,PL 1', 4, 'D.', 'regular', 'College Secretary', '08:00', '17:00', NULL, 't');
INSERT INTO "public"."instructors" VALUES (35, 'Allan Patrick', 'Aninon', 'allan.patrick', 'IT 104,IT 102,IC 1,PATHFIT 3', 4, NULL, 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (19, 'Kevin', 'Ramirez', 'kramirez', 'IT 102,ProE 1,PAN1', 4, 'M.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (8, 'Cathy', 'Ong', 'cong', 'ProE 1,IT 102,IT 104', 4, 'B.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (6, 'Andrew', 'Binibirocha', 'abinibirocha', 'IT 102,PAN1,IT 104', 4, 'E.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (20, 'Ana', 'Villanueva', 'avillanueva', 'PAN1,ProE 1,IT 102,IT 104', 4, 'N.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (9, 'Ella', 'Rivera', 'erivera', 'GE - RVA,ProE 1,IT 102,GEE - RVA', 4, 'C.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (7, 'Leo', 'Dizon', 'ldizon', 'GE - RVA,ProE 1,PAN1,IT 102,GEE - RVA', 4, 'A.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (29, 'Victor', 'Ocampo', 'vocampo', 'CS PROF ELECT 8,NC 101,TH 102,TE  3,TE 5,PROE 4,PATHFIT 1,IC 10,IC 9', 4, 'W.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (30, 'Zachary', 'Salazar', 'zsalazar', 'PATHFIT 3,CS PROF ELECT 8,HCI 101,PROE 2,PROF.3 E,IS 222,IC 1,PROF.E 1', 4, 'X.', 'regular', NULL, NULL, NULL, NULL, 't');
INSERT INTO "public"."instructors" VALUES (36, 'test', 'testing', 'test', 'CC 101,CS Prof Elect 6,PL 1,CS Prof Elect 7,CS Prof Elect 8,SP 1,GE - E,GE - CW,CC 105', 4, NULL, 'regular', 'College Secretary', NULL, NULL, NULL, 't');

-- ----------------------------
-- Table structure for rooms
-- ----------------------------
DROP TABLE IF EXISTS "public"."rooms";
CREATE TABLE "public"."rooms" (
  "id" int4 NOT NULL DEFAULT nextval('rooms_id_seq'::regclass),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "type" varchar(10) COLLATE "pg_catalog"."default" NOT NULL,
  "cluster" int4,
  "capacity" int4 DEFAULT 0,
  "description" text COLLATE "pg_catalog"."default",
  "building_id" int4,
  "is_available" bool NOT NULL DEFAULT true,
  "college_id" int4
)
;

-- ----------------------------
-- Records of rooms
-- ----------------------------
INSERT INTO "public"."rooms" VALUES (19, 'GYM', 'LEC', 0, 0, '', 9, 't', NULL);
INSERT INTO "public"."rooms" VALUES (23, 'CLAMS ROOM 1', 'LEC', 0, 0, '', 6, 't', 6);
INSERT INTO "public"."rooms" VALUES (24, 'CLAMS ROOM 2', 'LEC', 0, 0, '', 6, 't', 6);
INSERT INTO "public"."rooms" VALUES (25, 'CLAMS ROOM 3', 'LEC', 0, 0, '', 6, 't', 6);
INSERT INTO "public"."rooms" VALUES (26, 'COE ROOM 1', 'LEC', 0, 0, '', 2, 't', 8);
INSERT INTO "public"."rooms" VALUES (27, 'COE ROOM 2', 'LEC', 0, 0, '', 2, 't', 8);
INSERT INTO "public"."rooms" VALUES (28, 'COE ROOM 3', 'LEC', 0, 0, '', 2, 't', 8);
INSERT INTO "public"."rooms" VALUES (32, 'Inner Quad', 'LEC', 0, 0, 'INNER QUAD ROOM', 10, 't', NULL);
INSERT INTO "public"."rooms" VALUES (7, 'Phys Lab', 'LEC', 0, 0, '', 1, 't', NULL);
INSERT INTO "public"."rooms" VALUES (8, 'Bio Lab', 'LEC', 0, 0, '', 1, 't', NULL);
INSERT INTO "public"."rooms" VALUES (9, 'GS ER 1', 'LEC', 0, 0, '', 5, 't', NULL);
INSERT INTO "public"."rooms" VALUES (10, 'GS ER 2', 'LEC', 0, 0, '', 5, 't', NULL);
INSERT INTO "public"."rooms" VALUES (11, 'GS ER 3', 'LEC', 0, 0, '', 5, 't', NULL);
INSERT INTO "public"."rooms" VALUES (12, 'GS ER 4', 'LEC', 0, 0, '', 5, 't', NULL);
INSERT INTO "public"."rooms" VALUES (13, 'GS ER 5', 'LEC', 0, 0, '', 5, 't', NULL);
INSERT INTO "public"."rooms" VALUES (14, 'GS ER 6', 'LEC', 0, 0, '', 5, 't', NULL);
INSERT INTO "public"."rooms" VALUES (15, 'GS ER 7', 'LEC', 0, 0, '', 5, 't', NULL);
INSERT INTO "public"."rooms" VALUES (16, 'GS ER 8', 'LEC', 0, 0, '', 5, 't', NULL);
INSERT INTO "public"."rooms" VALUES (4, 'Comp Lab 1', 'LAB', 2, 0, '', 1, 't', NULL);
INSERT INTO "public"."rooms" VALUES (5, 'Comp Lab 2', 'LAB', 2, 0, '', 1, 't', NULL);
INSERT INTO "public"."rooms" VALUES (6, 'Comp Lab 3', 'LAB', 2, 0, '', 1, 't', NULL);
INSERT INTO "public"."rooms" VALUES (17, 'FIELD', 'LEC', 1, 100, '', 8, 't', NULL);

-- ----------------------------
-- Table structure for schedules
-- ----------------------------
DROP TABLE IF EXISTS "public"."schedules";
CREATE TABLE "public"."schedules" (
  "id" int4 NOT NULL DEFAULT nextval('schedules_id_seq'::regclass),
  "subject_id" int4,
  "instructor_id" int4,
  "room_id" int4,
  "course_id" int4 NOT NULL,
  "day_id" int4,
  "time" varchar(50) COLLATE "pg_catalog"."default",
  "year" int4 NOT NULL,
  "semester" int4 NOT NULL,
  "block" varchar(12) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Records of schedules
-- ----------------------------
INSERT INTO "public"."schedules" VALUES (12090, 141, 1, 7, 1, 1, '7:00 AM - 8:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12091, 141, 1, 7, 1, 3, '7:00 AM - 8:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12092, 141, 2, 8, 1, 1, '7:00 AM - 8:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12093, 141, 2, 8, 1, 3, '7:00 AM - 8:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12094, 141, 3, 9, 1, 1, '7:00 AM - 8:30 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12095, 141, 3, 9, 1, 3, '7:00 AM - 8:30 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12096, 146, 2, 7, 1, 1, '8:30 AM - 10:00 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12097, 146, 2, 7, 1, 3, '8:30 AM - 10:00 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12098, 146, 3, 9, 1, 1, '8:30 AM - 10:00 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12099, 146, 3, 9, 1, 3, '8:30 AM - 10:00 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12100, 146, 4, 10, 1, 1, '8:30 AM - 10:00 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12101, 146, 4, 10, 1, 3, '8:30 AM - 10:00 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12102, 140, 2, 9, 1, 1, '10:30 AM - 11:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12103, 140, 2, 9, 1, 3, '10:30 AM - 11:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12104, 140, 3, 10, 1, 1, '10:30 AM - 11:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12105, 140, 3, 10, 1, 3, '10:30 AM - 11:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12106, 140, 5, 11, 1, 1, '10:30 AM - 11:30 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12107, 140, 5, 11, 1, 3, '10:30 AM - 11:30 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12108, 138, 2, 8, 1, 1, '1:00 PM - 2:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12109, 138, 2, 8, 1, 3, '1:00 PM - 2:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12110, 138, 3, 9, 1, 1, '1:00 PM - 2:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12111, 138, 3, 9, 1, 3, '1:00 PM - 2:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12112, 138, 4, 10, 1, 1, '1:00 PM - 2:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12113, 138, 4, 10, 1, 3, '1:00 PM - 2:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12114, 139, 1, 7, 1, 1, '2:00 PM - 3:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12115, 139, 1, 7, 1, 3, '2:00 PM - 3:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12116, 139, 2, 8, 1, 1, '2:00 PM - 3:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12117, 139, 2, 8, 1, 3, '2:00 PM - 3:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12118, 139, 3, 9, 1, 1, '2:00 PM - 3:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12119, 139, 3, 9, 1, 3, '2:00 PM - 3:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12120, 145, 1, 7, 1, 1, '3:00 PM - 5:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12121, 145, 1, 7, 1, 3, '3:00 PM - 5:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12122, 145, 2, 8, 1, 1, '4:00 PM - 5:30 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12123, 145, 2, 8, 1, 3, '4:00 PM - 5:30 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12124, 145, 1, 7, 1, 1, '5:30 PM - 7:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12125, 145, 1, 7, 1, 3, '5:30 PM - 7:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12126, 142, 1, 4, 1, 2, '7:00 AM - 8:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12127, 142, 1, 4, 1, 4, '7:00 AM - 8:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12128, 142, 2, 4, 1, 2, '8:00 AM - 9:00 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12129, 142, 2, 4, 1, 4, '8:00 AM - 9:00 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12130, 142, 2, 4, 1, 5, '9:00 AM - 10:00 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12131, 143, 1, 16, 1, 2, '1:00 PM - 2:30 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12132, 143, 1, 16, 1, 4, '1:00 PM - 2:30 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12133, 143, 2, 7, 1, 2, '7:00 AM - 8:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12134, 143, 2, 7, 1, 4, '7:00 AM - 8:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12135, 143, 1, 8, 1, 2, '7:30 AM - 9:00 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12136, 143, 1, 8, 1, 4, '7:30 AM - 9:00 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12137, 144, 1, 4, 1, 2, '10:30 AM - 11:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12138, 144, 1, 4, 1, 4, '10:30 AM - 11:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12139, 144, 18, 6, 1, 5, '9:00 AM - 10:00 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12140, 144, 22, 5, 1, 2, '3:00 PM - 5:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12141, 144, 22, 5, 1, 4, '3:00 PM - 5:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12142, 147, 8, 17, 1, 7, 'SUN 8:00–11:00', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12143, 6, 7, 5, 4, 1, '7:00 AM - 8:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12144, 6, 7, 5, 4, 3, '7:00 AM - 8:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12145, 7, 4, 10, 4, 1, '7:00 AM - 8:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12146, 7, 4, 10, 4, 3, '7:00 AM - 8:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12147, 4, 5, 10, 4, 1, '2:30 PM - 4:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12148, 4, 5, 10, 4, 3, '2:30 PM - 4:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12149, 4, 6, 10, 4, 1, '4:00 PM - 5:30 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12150, 4, 6, 10, 4, 3, '4:00 PM - 5:30 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12151, 3, 2, 9, 4, 1, '5:30 PM - 7:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12152, 3, 2, 9, 4, 3, '5:30 PM - 7:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12153, 3, 6, 8, 4, 1, '11:00 AM - 12:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12154, 3, 6, 8, 4, 3, '11:00 AM - 12:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12155, 9, 7, 12, 4, 1, '1:00 PM - 2:30 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12156, 9, 7, 12, 4, 3, '1:00 PM - 2:30 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12157, 9, 6, 11, 4, 1, '9:00 AM - 10:00 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12158, 9, 6, 11, 4, 3, '9:00 AM - 10:00 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12159, 10, 1, 7, 4, 1, '11:00 AM - 12:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12160, 10, 1, 7, 4, 3, '11:00 AM - 12:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12161, 10, 6, 11, 4, 1, '1:00 PM - 3:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12162, 10, 6, 11, 4, 3, '1:00 PM - 3:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12163, 5, 2, 16, 4, 2, '9:00 AM - 10:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12164, 5, 2, 16, 4, 4, '9:00 AM - 10:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12165, 5, 2, 10, 4, 2, '9:00 AM - 11:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12166, 5, 2, 10, 4, 4, '9:00 AM - 11:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12167, 8, 4, 5, 4, 2, '7:30 AM - 8:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12168, 8, 4, 5, 4, 4, '7:30 AM - 8:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12169, 8, 36, 6, 4, 2, '7:00 AM - 8:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12170, 8, 36, 6, 4, 4, '7:00 AM - 8:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12171, 226, 13, 17, 4, 7, 'SUN 8:00–11:00', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12172, 6, 1, 4, 4, 1, '9:00 AM - 10:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12173, 6, 1, 4, 4, 3, '9:00 AM - 10:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12174, 7, 1, 7, 4, 5, '7:00 AM - 8:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12175, 134, 12, 4, 3, 1, '7:00 AM - 8:30 AM', 4, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12176, 134, 12, 4, 3, 3, '7:00 AM - 8:30 AM', 4, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12177, 134, 18, 6, 3, 1, '7:00 AM - 8:30 AM', 4, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12178, 134, 18, 6, 3, 3, '7:00 AM - 8:30 AM', 4, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12179, 134, 12, 5, 3, 1, '9:00 AM - 10:00 AM', 4, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12180, 134, 12, 5, 3, 3, '9:00 AM - 10:00 AM', 4, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12181, 132, 24, 11, 3, 1, '7:00 AM - 8:30 AM', 4, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12182, 132, 24, 11, 3, 3, '7:00 AM - 8:30 AM', 4, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12183, 135, 12, 7, 3, 1, '10:30 AM - 11:30 AM', 4, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12184, 135, 12, 7, 3, 3, '10:30 AM - 11:30 AM', 4, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12185, 135, 18, 12, 3, 1, '9:00 AM - 10:00 AM', 4, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12186, 135, 18, 12, 3, 3, '9:00 AM - 10:00 AM', 4, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12187, 135, 12, 7, 3, 1, '1:00 PM - 2:00 PM', 4, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12188, 135, 12, 7, 3, 3, '1:00 PM - 2:00 PM', 4, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12189, 133, 24, 6, 3, 1, '8:30 AM - 10:00 AM', 4, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12190, 133, 24, 6, 3, 3, '8:30 AM - 10:00 AM', 4, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12191, 133, 24, 6, 3, 1, '1:00 PM - 3:00 PM', 4, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12192, 133, 24, 6, 3, 3, '1:00 PM - 3:00 PM', 4, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12193, 133, 24, 4, 3, 1, '10:30 AM - 11:30 AM', 4, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12194, 133, 24, 4, 3, 3, '10:30 AM - 11:30 AM', 4, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12195, 131, 21, 4, 3, 1, '1:00 PM - 2:00 PM', 4, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12196, 131, 21, 4, 3, 3, '1:00 PM - 2:00 PM', 4, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12197, 131, 21, 5, 3, 1, '10:30 AM - 11:30 AM', 4, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12198, 131, 21, 5, 3, 3, '10:30 AM - 11:30 AM', 4, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12199, 131, 12, 5, 3, 2, '8:30 AM - 10:00 AM', 4, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12200, 131, 12, 5, 3, 4, '8:30 AM - 10:00 AM', 4, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12201, 132, 24, 7, 3, 2, '8:30 AM - 10:00 AM', 4, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12202, 132, 24, 7, 3, 4, '8:30 AM - 10:00 AM', 4, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12203, 132, 12, 7, 3, 2, '10:30 AM - 11:30 AM', 4, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12204, 132, 12, 7, 3, 4, '10:30 AM - 11:30 AM', 4, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12697, 97, 14, 8, 3, 2, '10:30 AM - 11:30 AM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12698, 97, 14, 8, 3, 4, '10:30 AM - 11:30 AM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12699, 97, 14, 7, 3, 5, '8:30 AM - 10:00 AM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12700, 98, 2, 19, 3, 2, '1:00 PM - 2:00 PM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12701, 98, 2, 19, 3, 4, '1:00 PM - 2:00 PM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12702, 98, 2, 19, 3, 2, '2:00 PM - 3:00 PM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12703, 98, 2, 19, 3, 4, '2:00 PM - 3:00 PM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12704, 92, 25, 5, 3, 1, '2:30 PM - 4:00 PM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12705, 92, 25, 5, 3, 3, '2:30 PM - 4:00 PM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12706, 92, 25, 5, 3, 1, '4:00 PM - 5:30 PM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12707, 92, 25, 5, 3, 3, '4:00 PM - 5:30 PM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12708, 93, 25, 7, 3, 5, '10:30 AM - 11:30 AM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12709, 93, 25, 7, 3, 5, '4:00 PM - 5:30 PM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12710, 89, 3, 5, 3, 1, '5:30 PM - 7:00 PM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12711, 89, 3, 5, 3, 3, '5:30 PM - 7:00 PM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12712, 89, 3, 6, 3, 2, '9:00 AM - 12:00 PM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12713, 89, 3, 6, 3, 4, '9:00 AM - 12:00 PM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12714, 95, 27, 4, 3, 2, '2:00 PM - 3:00 PM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12715, 95, 27, 4, 3, 4, '2:00 PM - 3:00 PM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12716, 95, 27, 4, 3, 5, '11:00 AM - 12:00 PM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12717, 90, 14, 8, 3, 5, '1:00 PM - 2:00 PM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12718, 90, 14, 7, 3, 5, '2:00 PM - 3:00 PM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12719, 96, 4, 7, 3, 5, '5:30 PM - 7:00 PM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12720, 94, 27, 8, 3, 5, '2:00 PM - 3:00 PM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12721, 94, 27, 8, 3, 5, '5:30 PM - 7:00 PM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12722, 91, 3, 23, 3, 5, '7:00 AM - 8:30 AM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12508, 84, 4, 6, 3, 1, '10:30 AM - 11:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12509, 84, 4, 6, 3, 3, '10:30 AM - 11:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12510, 84, 13, 5, 3, 1, '1:00 PM - 2:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12511, 84, 13, 5, 3, 3, '1:00 PM - 2:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12512, 84, 4, 4, 3, 2, '9:00 AM - 10:00 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12513, 84, 4, 4, 3, 4, '9:00 AM - 10:00 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12514, 80, 4, 8, 3, 5, '3:00 PM - 5:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12515, 80, 4, 8, 3, 5, '9:00 AM - 10:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12516, 80, 4, 8, 3, 5, '10:30 AM - 11:30 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12517, 78, 13, 7, 3, 2, '1:00 PM - 2:30 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12518, 78, 13, 7, 3, 4, '1:00 PM - 2:30 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12519, 78, 4, 8, 3, 2, '10:30 AM - 12:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12520, 78, 4, 8, 3, 4, '10:30 AM - 12:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12521, 78, 4, 8, 3, 2, '1:00 PM - 2:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12522, 78, 4, 8, 3, 4, '1:00 PM - 2:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12523, 79, 3, 7, 3, 2, '2:30 PM - 4:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12524, 79, 3, 7, 3, 4, '2:30 PM - 4:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12525, 79, 3, 7, 3, 2, '5:30 PM - 7:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12526, 79, 3, 7, 3, 4, '5:30 PM - 7:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12527, 79, 13, 8, 3, 1, '9:00 AM - 10:00 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12528, 79, 13, 8, 3, 3, '9:00 AM - 10:00 AM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12529, 85, 7, 8, 3, 2, '9:00 AM - 10:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12530, 85, 7, 8, 3, 4, '9:00 AM - 10:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12531, 85, 9, 8, 3, 1, '10:30 AM - 11:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12532, 85, 9, 8, 3, 3, '10:30 AM - 11:30 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12533, 85, 9, 8, 3, 1, '5:30 PM - 7:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12534, 85, 9, 8, 3, 3, '5:30 PM - 7:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12535, 82, 4, 4, 3, 1, '2:00 PM - 3:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12536, 82, 4, 4, 3, 3, '2:00 PM - 3:00 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12537, 82, 4, 4, 3, 1, '5:30 PM - 7:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12538, 82, 4, 4, 3, 3, '5:30 PM - 7:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12539, 82, 4, 4, 3, 1, '3:00 PM - 5:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12540, 82, 4, 4, 3, 3, '3:00 PM - 5:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12541, 81, 4, 7, 3, 2, '4:00 PM - 5:30 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12542, 81, 4, 7, 3, 4, '4:00 PM - 5:30 PM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12543, 81, 4, 8, 3, 2, '2:00 PM - 3:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12544, 81, 4, 8, 3, 4, '2:00 PM - 3:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12545, 81, 4, 8, 3, 2, '5:30 PM - 7:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12546, 81, 4, 8, 3, 4, '5:30 PM - 7:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12547, 83, 4, 8, 3, 5, '7:00 AM - 8:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12548, 83, 13, 8, 3, 2, '3:00 PM - 5:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12549, 83, 13, 8, 3, 4, '3:00 PM - 5:00 PM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12550, 83, 4, 7, 3, 5, '1:00 PM - 2:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12551, 86, 21, 19, 3, 1, '7:00 AM - 8:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12552, 86, 21, 19, 3, 3, '7:00 AM - 8:30 AM', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12553, 86, 21, 19, 3, 1, '8:30 AM - 10:00 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12554, 86, 21, 19, 3, 3, '8:30 AM - 10:00 AM', 1, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12555, 86, 21, 19, 3, 1, '2:00 PM - 3:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12556, 86, 21, 19, 3, 3, '2:00 PM - 3:00 PM', 1, 1, 'C');
INSERT INTO "public"."schedules" VALUES (12557, 87, 13, 17, 3, 7, 'SUN 8:00–11:00', 1, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12723, 91, 3, 23, 3, 2, '7:00 AM - 8:30 AM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12724, 91, 3, 23, 3, 4, '7:00 AM - 8:30 AM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12725, 99, 14, 32, 3, 2, '8:30 AM - 10:00 AM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12726, 99, 14, 32, 3, 4, '8:30 AM - 10:00 AM', 2, 1, 'A');
INSERT INTO "public"."schedules" VALUES (12727, 99, 14, 32, 3, 1, '7:00 AM - 8:30 AM', 2, 1, 'B');
INSERT INTO "public"."schedules" VALUES (12728, 99, 14, 32, 3, 3, '7:00 AM - 8:30 AM', 2, 1, 'B');

-- ----------------------------
-- Table structure for subjects
-- ----------------------------
DROP TABLE IF EXISTS "public"."subjects";
CREATE TABLE "public"."subjects" (
  "id" int4 NOT NULL DEFAULT nextval('subjects_id_seq'::regclass),
  "code" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default" NOT NULL,
  "type" varchar(10) COLLATE "pg_catalog"."default" NOT NULL,
  "unit" int4 NOT NULL,
  "recommended_slots" int4,
  "cluster" int4,
  "min_slots" int4,
  "max_slots" int4,
  "year_level" int4,
  "semester" int4,
  "course_id" int4,
  "is_major" bool,
  "is_block_shared" bool NOT NULL DEFAULT false
)
;

-- ----------------------------
-- Records of subjects
-- ----------------------------
INSERT INTO "public"."subjects" VALUES (148, 'GE - RVA', 'Reading Visual Art', 'LEC', 3, 4, 0, 2, 4, 1, 2, 1, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (111, 'ProE 1', 'Object-Oriented Programming', 'LEC', 3, 4, 2, 2, 4, 2, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (112, 'PAN1', 'Sinesosyedad/Pelikulang Panlipunan', 'LEC', 3, 4, 2, 2, 4, 2, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (162, 'IT 102', 'Information Assurance and Security 1', 'LAB', 1, 3, 1, 3, 3, 2, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (163, 'IT 102', 'Information Assurance and Security 1', 'LEC', 2, 4, 0, 2, 4, 2, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (164, 'IT 104', 'Social and Professional Issues', 'LEC', 3, 4, 0, 2, 4, 2, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (165, 'IC 1', 'Strategic Project Management in IT', 'LEC', 3, 4, 0, 2, 4, 2, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (166, 'PATHFIT 3', 'Physical Activities Towards Health 3', 'LEC', 2, 4, 0, 2, 4, 2, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (186, 'IC 3', 'Research Methods in Computing', 'LEC', 3, 4, 2, 2, 4, 3, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (15, 'CC 103', 'Intermediate Programming', 'LAB', 1, 3, 2, 3, 3, 1, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (195, 'IT 110', 'Systems integration and Architecture 1', 'LEC', 3, 4, 2, 2, 4, 3, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (77, 'TH 102', 'Thesis 2', 'LEC', 3, 6, 1, 2, 4, 4, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (210, 'CAP 2', 'Capstone 2', 'LEC', 2, 4, 2, 2, 4, 4, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (171, 'GE - E', 'Ethics', 'LEC', 3, 4, 2, 2, 4, 2, 2, 1, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (172, 'GE - CW', 'The Contemporary World', 'LEC', 3, 4, 2, 2, 4, 2, 2, 1, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (226, 'NSTP 1', 'National Service Training Program 1', 'LEC', 3, 1, 2, 2, 4, 1, 1, 4, 'f', 't');
INSERT INTO "public"."subjects" VALUES (180, 'IT 107', 'Information Assurance & Security 2', 'LEC', 3, 4, 2, 2, 4, 2, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (200, 'ProE 5', 'Systems Integration and Architecture 2', 'LEC', 2, 4, 1, 2, 4, 3, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (132, 'IS 412', 'Capstone 1', 'LEC', 2, 4, 1, 2, 4, 4, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (134, 'ProE 7', 'Certification Review, Training and Seminar 1', 'LAB', 1, 3, 0, 3, 3, 4, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (135, 'ProE 7', 'Certification Review, Training and Seminar 2', 'LEC', 2, 4, 1, 2, 4, 4, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (3, 'GE - MM', 'Mathematics in the Modern World', 'LEC', 3, 4, 0, 2, 4, 1, 1, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (4, 'FIL1', 'Kontekstwalisadong Komunikasyon sa Filipino', 'LEC', 3, 4, 0, 2, 4, 1, 1, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (5, 'CC 101', 'Introduction to Computing', 'LEC', 2, 4, 0, 2, 4, 1, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (6, 'CC 101', 'Introduction to Computing', 'LAB', 1, 3, 0, 3, 3, 1, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (30, 'CC 105', 'Information Management', 'LAB', 1, 3, 1, 3, 3, 2, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (31, 'GE - E', 'Ethics', 'LEC', 3, 4, 0, 2, 4, 2, 2, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (11, 'GE - PH', 'Readings in Philippine History', 'LEC', 3, 4, 0, 2, 4, 1, 2, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (32, 'RIZAL', 'Rizal''s Life & Works', 'LEC', 3, 4, 0, 2, 4, 2, 2, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (33, 'CS Prof Elect 2', 'Introduction to Data Science', 'LEC', 3, 4, 0, 2, 4, 2, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (28, 'PE 21', 'Physical Activities Towards Health & Fitness 1', 'LEC', 2, 4, 2, 2, 4, 2, 1, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (38, 'PE 22', 'Physical Activities Towards Health & Fitness 2', 'LEC', 2, 4, 2, 2, 4, 2, 2, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (34, 'Acct 1', 'Fundamentals of Accounting', 'LEC', 3, 4, 0, 2, 4, 2, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (35, 'CS Prof Elect 3', 'Web Systems & Technologies', 'LAB', 1, 3, 1, 3, 3, 2, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (37, 'AL 101', 'Algorithms & Complexity', 'LEC', 3, 4, 0, 2, 4, 2, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (24, 'SDF 104', 'Object-Oriented Programming', 'LEC', 2, 4, 2, 2, 4, 2, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (99, 'GE - US', 'Understanding the Self', 'LEC', 3, 4, 2, 2, 4, 2, 1, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (55, 'CS Elect 2 - IS 101', 'Intelligent System (Machine Learning)', 'LAB', 1, 3, 1, 3, 3, 3, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (27, 'CS Prof Elect 1', 'Digital Design', 'LEC', 2, 4, 2, 2, 4, 2, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (72, 'CS Prof Elect 9', 'Certification Review Training & Seminar', 'LEC', 3, 4, 2, 2, 4, 4, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (64, 'CS Elect 3-PD 101', 'Parallel and Distributed Computing', 'LEC', 2, 4, 0, 2, 4, 4, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (65, 'CS Elect 3-PD 101', 'Parallel and Distributed Computing', 'LAB', 1, 3, 0, 3, 3, 4, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (36, 'CS Prof Elect 3', 'Web Systems & Technologies', 'LEC', 2, 4, 2, 2, 4, 2, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (54, 'CS Elect 2 - IS 101', 'Intelligent System (Machine Learning)', 'LEC', 2, 4, 2, 2, 4, 3, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (56, 'CS Prof Elect 6', 'Natural Language Processing', 'LEC', 3, 4, 2, 2, 4, 3, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (174, 'CC 105', 'Information Management', 'LEC', 1, 4, 0, 2, 4, 2, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (184, 'CC 106', 'Application Development and Emerging Technologies', 'LEC', 2, 4, 2, 2, 4, 3, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (29, 'CC 105', 'Information Management', 'LEC', 2, 4, 2, 2, 4, 2, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (175, 'Prof.E 2', 'Web Systems & Technologies', 'LEC', 2, 4, 0, 2, 4, 2, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (177, 'PATHFIT 4', 'Physical Activities Towards Health 4', 'LEC', 2, 4, 0, 2, 4, 2, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (179, 'IC 2', 'Virtualization and Cloud Platforms', 'LEC', 2, 4, 0, 2, 4, 2, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (182, 'Prof.E 1', 'Object-Oriented Programming', 'LEC', 2, 4, 0, 2, 4, 2, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (52, 'SE 1', 'Software Engineering', 'LAB', 1, 3, 1, 3, 3, 3, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (53, 'Res 1', 'Method of Research in Computing', 'LEC', 3, 6, 0, 2, 4, 3, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (66, 'OS 101', 'Operating Systems', 'LEC', 3, 4, 2, 2, 4, 4, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (187, 'Prof.3 E', 'Integrative Programming Technologies 2', 'LEC', 2, 4, 2, 2, 4, 3, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (209, 'Prof.E 8', 'Cybersecurity', 'LAB', 3, 3, 2, 3, 3, 4, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (133, 'IS 412', 'Capstone 1', 'LAB', 1, 3, 1, 3, 3, 4, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (130, 'ProE 6', 'Methods of Research in Computing', 'LEC', 3, 4, 0, 2, 4, 3, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (136, 'IS 421', 'Capstone 2', 'LEC', 2, 4, 0, 2, 4, 4, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (67, 'HCI 101', 'Human Computer Interaction', 'LEC', 1, 4, 0, 2, 4, 4, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (68, 'SE 2', 'Software Engineering 2', 'LEC', 2, 4, 0, 2, 4, 4, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (69, 'SE 2', 'Software Engineering 2', 'LAB', 1, 3, 0, 3, 3, 4, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (51, 'SE 1', 'Software Engineering', 'LEC', 2, 4, 2, 2, 4, 3, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (57, 'PL 1', 'Programming Languages', 'LEC', 2, 4, 2, 2, 4, 3, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (58, 'PL 1', 'Programming Languages', 'LAB', 1, 3, 2, 3, 3, 3, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (153, 'CC 103', 'Computer Programming 2', 'LEC', 2, 4, 2, 2, 4, 1, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (173, 'CC 105', 'Information Management', 'LAB', 2, 3, 0, 3, 3, 2, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (176, 'Prof.E 2', 'Web Systems & Technologies', 'LAB', 1, 3, 0, 3, 3, 2, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (178, 'IC 2', 'Virtualization and Cloud Platforms', 'LAB', 1, 3, 0, 3, 3, 2, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (196, 'IC 5', 'Mobile Application Development', 'LEC', 2, 4, 1, 2, 4, 3, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (100, 'GE - E', 'Ethics', 'LEC', 3, 4, 2, 2, 4, 2, 2, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (101, 'GE - CW', 'The Contemporary World', 'LEC', 3, 4, 2, 2, 4, 2, 2, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (198, 'IC 6', 'Entrepreneurship', 'LEC', 3, 4, 2, 2, 4, 3, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (199, 'IT 113', 'Systems Administration and Maintenance', 'LEC', 1, 4, 1, 2, 4, 3, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (204, 'IT 114', 'Networking 2', 'LAB', 1, 3, 0, 3, 3, 3, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (206, 'ProE 7', 'Human Computer Interaction 2', 'LAB', 1, 3, 0, 3, 3, 3, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (113, 'CC 106', 'Application Development and Emerging Technologies', 'LEC', 2, 4, 1, 2, 4, 3, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (102, 'CC 105', 'Information Management', 'LAB', 2, 3, 0, 3, 3, 2, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (103, 'CC 105', 'Information Management', 'LEC', 1, 4, 1, 2, 4, 2, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (109, 'IS 221', 'IT Infrastructure & Network Technologies', 'LEC', 3, 4, 2, 2, 4, 2, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (116, 'TE 5', 'Advance Database Systems', 'LEC', 2, 4, 1, 2, 4, 3, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (185, 'CC 106', 'Application Development and Emerging Technologies', 'LAB', 1, 3, 2, 3, 3, 3, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (212, 'IC 10', 'Certification Review, Training and Seminar 1', 'LAB', 1, 3, 1, 3, 3, 4, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (214, 'IC 9', 'Field Trips and Exposure', 'LAB', 1, 3, 1, 3, 3, 4, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (167, 'IT 103', 'Fundamentals of Database Systems', 'LAB', 1, 3, 1, 3, 3, 2, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (110, 'IS 222', 'Enterprise Architecture', 'LEC', 3, 4, 2, 2, 4, 2, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (168, 'IT 103', 'Fundamentals of Database Systems', 'LEC', 2, 4, 0, 2, 4, 2, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (169, 'IT 104', 'Networking 1', 'LAB', 1, 3, 1, 3, 3, 2, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (170, 'IT 104', 'Networking 1', 'LEC', 2, 4, 0, 2, 4, 2, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (189, 'IT 109', 'Quantitative Methods (incl. Modeling & Simulation)', 'LEC', 3, 4, 2, 2, 4, 3, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (192, 'Prof.4 E', 'Platform Technologies 1', 'LEC', 3, 4, 2, 2, 4, 3, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (139, 'GE - PC', 'Purposive Communication', 'LEC', 3, 4, 2, 2, 4, 1, 1, 1, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (227, 'NSTP 2', 'National Service Training Program 2', 'LEC', 3, 1, 1, 2, 4, 1, 2, 4, 'f', 't');
INSERT INTO "public"."subjects" VALUES (13, 'GE - CW', 'The Contemporary World', 'LEC', 3, 4, 0, 2, 4, 1, 2, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (16, 'GE - PC', 'Purposive Communication', 'LEC', 3, 4, 0, 2, 4, 1, 2, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (191, 'IT 111', 'Advance Database System', 'LAB', 1, 3, 1, 3, 3, 3, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (194, 'IC 4', 'Multimedia System', 'LAB', 1, 3, 1, 3, 3, 3, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (18, 'PE 12', 'Fitness Exercise (FE)', 'LEC', 2, 4, 2, 2, 4, 1, 2, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (12, 'FIL2', 'Filipino sa Iba''t Ibang Disiplina', 'LEC', 3, 4, 0, 2, 4, 1, 2, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (17, 'DS 101', 'Discrete Structure 1', 'LEC', 3, 4, 0, 2, 4, 1, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (114, 'CC 106', 'Application Development and Emerging Technologies', 'LAB', 1, 3, 1, 3, 3, 3, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (14, 'CC 103', 'Intermediate Programming', 'LEC', 2, 4, 2, 2, 4, 1, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (93, 'TE 2', 'Intro to 2D Animation', 'LEC', 2, 4, 0, 2, 4, 2, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (94, 'IS 211', 'Quantitative Methods ', 'LEC', 3, 4, 2, 2, 4, 2, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (96, 'FIL2', 'Filipino sa Iba’t Ibang Disiplina ', 'LEC', 3, 4, 2, 2, 4, 2, 1, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (97, 'IS 213', 'Financial Management ', 'LEC', 2, 4, 0, 2, 4, 2, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (137, 'IS 421', 'Capstone 2', 'LAB', 1, 3, 1, 3, 3, 4, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (98, 'PE 21', 'Physical Activities Towards Health & Fitness (PATH-Fit) 1 (Dance, Sports, Outdoor & Adventure Activities)', 'LEC', 2, 4, 0, 2, 4, 2, 1, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (190, 'IT 111', 'Advance Database System', 'LEC', 2, 4, 2, 2, 4, 3, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (124, 'IS 321', 'Platform-based Development', 'LEC', 2, 4, 2, 2, 4, 3, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (127, 'ProE 5', 'IT Security & Management', 'LEC', 1, 4, 2, 2, 4, 3, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (193, 'IC 4', 'Multimedia System', 'LEC', 2, 4, 2, 2, 4, 3, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (128, 'ProE 4', 'IS Project Management 2', 'LEC', 2, 4, 2, 2, 4, 3, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (197, 'IC 5', 'Mobile Application Development', 'LAB', 1, 3, 1, 3, 3, 3, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (216, 'IT PRC', 'Practicum', 'LAB', 6, 6, 0, 3, 3, 4, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (95, 'IS 212', 'Organization & Management Concept ', 'LAB', 1, 3, 1, 3, 3, 2, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (217, 'GE - PH', 'Readings in Philippine History', 'LEC', 3, 1, 2, 2, 4, 1, 2, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (218, 'RIZAL', 'Rizal’s Life & Works', 'LEC', 3, 1, 2, 2, 4, 1, 2, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (201, 'ProE 5', 'Systems Integration and Architecture 2', 'LAB', 1, 3, 1, 3, 3, 3, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (115, 'IS 313', 'System Analysis & Design', 'LEC', 3, 4, 2, 2, 4, 3, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (126, 'IS 322', 'Professional Issues in Information Systems', 'LEC', 3, 4, 0, 2, 4, 3, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (117, 'TE 5', 'Advance Database Systems', 'LAB', 1, 3, 1, 3, 3, 3, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (118, 'ProE 2', 'Enterprise System', 'LEC', 3, 4, 2, 2, 4, 3, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (20, 'CC 104', 'Data Structures & Algorithms 3', 'LEC', 3, 4, 0, 2, 4, 2, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (149, 'GE - PH', 'Readings in Philippine History & Studies of Indigenous People', 'LEC', 3, 4, 0, 2, 4, 1, 2, 1, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (150, 'GE -RIZAL', 'Rizal''s Life & Works', 'LEC', 3, 4, 0, 2, 4, 1, 2, 1, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (151, 'IT 101', 'Introduction to Human Computer Interaction', 'LEC', 2, 4, 2, 2, 4, 1, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (152, 'IT 101', 'Introduction to Human Computer Interaction', 'LAB', 1, 3, 2, 3, 3, 1, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (78, 'GE - MM', 'Mathematics in the Modern World', 'LEC', 3, 4, 1, 2, 4, 1, 1, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (141, 'CC 101', ' Introduction to Computing', 'LEC', 2, 4, 0, 2, 4, 1, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (79, 'GE - PC', 'Purposive Communication', 'LEC', 3, 4, 1, 2, 4, 1, 1, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (80, 'FIL1', 'Kontekstwalisadong Komunikasyon sa Filipino', 'LEC', 3, 4, 1, 2, 4, 1, 1, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (84, 'CC 102', 'Fundamentals of Programming', 'LAB', 1, 3, 0, 3, 3, 1, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (142, 'CC 101', ' Introduction to Computing', 'LAB', 1, 3, 0, 3, 3, 1, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (143, 'CC 102', 'Computer Programming 1', 'LEC', 2, 4, 0, 2, 4, 1, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (144, 'CC 102', 'Computer Programming 1', 'LAB', 1, 3, 0, 3, 3, 1, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (75, 'NC 101', 'Network and Communication', 'LAB', 2, 3, 0, 3, 3, 4, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (219, 'CC 103', 'Intermediate Programming', 'LEC', 2, 1, 0, 2, 4, 1, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (76, 'NC 101', 'Network and Communication', 'LEC', 1, 4, 2, 2, 4, 4, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (181, 'IT 108', 'Integrative Programming and Technologies 1', 'LEC', 3, 4, 2, 2, 4, 2, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (220, 'CC 103', 'Intermediate Programming', 'LAB', 1, 1, 0, 3, 3, 1, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (119, 'IS 311', 'IS Project Management 1', 'LEC', 2, 4, 1, 2, 4, 3, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (222, 'TE 1', 'Multimedia Systems', 'LEC', 2, 1, 0, 2, 4, 1, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (223, 'TE 1', 'Multimedia Systems', 'LAB', 1, 1, 0, 3, 3, 1, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (88, 'GE - AA', 'Art Appreciation', 'LEC', 3, 4, 1, 2, 4, 1, 2, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (221, 'IS 121', 'Fundamentals of Information Systems', 'LEC', 3, 1, 2, 2, 4, 1, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (122, 'ProE 3', 'IS Innovation & New Technologies', 'LEC', 2, 4, 1, 2, 4, 3, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (39, 'CS Elect 1 - GV 101', 'Graphics & Visual Computing', 'LAB', 1, 3, 1, 3, 3, 3, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (40, 'CS Elect 1 - GV 101', 'Graphics & Visual Computing', 'LEC', 2, 4, 0, 2, 4, 3, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (41, 'AR 101', 'Computer Architecture & Organization', 'LAB', 1, 3, 1, 3, 3, 3, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (158, 'CC 104', 'Data Structures & Algorithms ', 'LEC', 2, 4, 0, 2, 4, 2, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (159, 'CC 104', 'Data Structures & Algorithms ', 'LAB', 1, 3, 0, 3, 3, 2, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (160, 'IT 106', 'Discrete Mathematics', 'LEC', 3, 4, 0, 2, 4, 2, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (161, 'GE - ST', 'Science, Technology & Society', 'LEC', 3, 4, 0, 2, 4, 2, 1, 1, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (138, 'GE - MM', 'Mathematics in the Modern World', 'LEC', 3, 4, 2, 2, 4, 1, 1, 1, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (140, 'GE - GCP', 'Gender, Conflict and Peace', 'LEC', 3, 4, 2, 2, 4, 1, 1, 1, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (145, 'PATHFIT 1', 'Physical Activities Towards Health 1', 'LEC', 3, 4, 2, 2, 4, 1, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (146, 'GE - AA', 'Art Appreciation', 'LEC', 3, 4, 2, 2, 4, 1, 1, 1, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (147, 'NSTP 1', 'National Service Training Program 1', 'LEC', 3, 4, 2, 2, 4, 1, 1, 1, 'f', 't');
INSERT INTO "public"."subjects" VALUES (42, 'AR 101', 'Computer Architecture & Organization', 'LEC', 2, 4, 0, 2, 4, 3, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (43, 'CS Prof Elect 4', 'Digital Image Processing', 'LAB', 1, 3, 1, 3, 3, 3, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (44, 'CS Prof Elect 4', 'Digital Image Processing', 'LEC', 2, 4, 0, 2, 4, 3, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (46, 'AL 2', 'Automata Theory & Formal Language', 'LEC', 3, 4, 0, 2, 4, 3, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (47, 'IAS 1', 'Information Assurance & Security', 'LEC', 2, 4, 0, 2, 4, 3, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (90, 'AMR', 'Discrete Mathematics', 'LEC', 3, 4, 2, 2, 4, 2, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (91, 'GE - ST', 'Science, Technology & Society', 'LEC', 3, 4, 2, 2, 4, 2, 1, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (92, 'TE 2', 'Intro to 2D Animation', 'LAB', 1, 3, 0, 3, 3, 2, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (125, 'IS 321', 'Platform-based Development', 'LAB', 1, 3, 2, 3, 3, 3, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (22, 'GE - ST', 'Science Technology & Society', 'LEC', 3, 4, 0, 2, 4, 2, 1, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (129, 'ProE 4', 'IS Project Management 2', 'LAB', 1, 3, 2, 3, 3, 3, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (23, 'SDF 104', 'Object-Oriented Programming', 'LAB', 1, 3, 2, 3, 3, 2, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (25, 'PAN 1', 'Sinesosyedad/Pelikulang Panlipunan', 'LEC', 3, 4, 0, 2, 4, 2, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (74, 'CS Prof Elect 10', 'Android Application Development', 'LAB', 1, 3, 1, 3, 3, 4, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (26, 'CS Prof Elect 1', 'Digital Design', 'LAB', 1, 3, 2, 3, 3, 2, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (45, 'Stat 1', 'Statistics in Computing', 'LEC', 3, 6, 2, 2, 4, 3, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (120, 'IS 311', 'IS Project Management 1', 'LAB', 1, 3, 1, 3, 3, 3, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (121, 'IS 312', 'Business Process Management', 'LEC', 3, 4, 2, 2, 4, 3, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (123, 'ProE 3', 'IS Innovation & New Technologies', 'LAB', 1, 3, 1, 3, 3, 3, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (131, 'IS 411', 'Evaluation of Business Performance', 'LAB', 3, 3, 2, 3, 3, 4, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (71, 'THS 101', 'Thesis 1', 'LAB', 1, 3, 1, 3, 3, 4, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (21, 'DS 102', 'Discrete Structure 2', 'LEC', 3, 4, 0, 2, 4, 2, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (211, 'CAP 2', 'Capstone 2', 'LAB', 1, 3, 2, 3, 3, 4, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (213, 'IC 10', 'Certification Review, Training and Seminar 2', 'LEC', 2, 4, 2, 2, 4, 4, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (154, 'CC 103', 'Computer Programming 2', 'LAB', 1, 3, 2, 3, 3, 1, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (155, 'PATHFIT 2', 'Physical Activities Towards Health 2', 'LEC', 2, 4, 2, 2, 4, 1, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (19, 'GE - AA', 'Art Appreciation', 'LEC', 3, 4, 0, 2, 4, 2, 1, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (157, 'GE - US', 'Understanding the Self', 'LEC', 3, 4, 0, 2, 4, 1, 2, 1, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (183, 'Prof.E 1', 'Object-Oriented Programming', 'LAB', 1, 3, 0, 3, 3, 2, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (104, 'TE  3', 'Web Systems & Technologies', 'LEC', 2, 4, 1, 2, 4, 2, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (105, 'TE  3', 'Web Systems & Technologies', 'LAB', 1, 3, 1, 3, 3, 2, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (106, 'PE 22', 'Physical Activities Towards Health & Fitness (PATH-Fit) 2 (Dance, Sports, Outdoor & Adventure Activities)', 'LEC', 2, 4, 1, 2, 4, 2, 2, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (107, 'TE 4', 'PC Troubleshooting and Networking', 'LAB', 1, 3, 0, 3, 3, 2, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (108, 'TE 4', 'PC Troubleshooting and Networking', 'LEC', 2, 4, 1, 2, 4, 2, 2, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (215, 'IC 9', 'Field Trips and Exposure', 'LEC', 2, 4, 2, 2, 4, 4, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (87, 'NSTP 1', 'National Service Training Program 1', 'LEC', 3, 4, 1, 2, 4, 1, 1, 3, 'f', 't');
INSERT INTO "public"."subjects" VALUES (156, 'NSTP 2', 'National Service Training Program 2', 'LEC', 3, 4, 0, 2, 4, 1, 2, 1, 'f', 't');
INSERT INTO "public"."subjects" VALUES (89, 'CC 104', 'Data Structures & Algorithms ', 'LAB', 1, 3, 1, 3, 3, 2, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (70, 'THS 101', 'Thesis 1', 'LEC', 2, 4, 0, 2, 4, 4, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (63, 'SP 1', 'Social Issues & Professional Practice', 'LEC', 3, 4, 2, 2, 4, 3, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (225, 'NSTP 2', 'National Service Training Program 2', 'LEC', 3, 1, 2, 2, 4, 1, 2, 3, 'f', 't');
INSERT INTO "public"."subjects" VALUES (73, 'CS Prof Elect 10', 'Android Application Development', 'LEC', 2, 4, 0, 2, 4, 4, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (59, 'CS Prof Elect 7', 'Platform-Based Development', 'LEC', 2, 4, 2, 2, 4, 3, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (60, 'CS Prof Elect 7', 'Platform-Based Development', 'LAB', 1, 3, 2, 3, 3, 3, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (61, 'CS Prof Elect 8', 'PC Troubleshooting & Networking', 'LEC', 2, 4, 2, 2, 4, 3, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (62, 'CS Prof Elect 8', 'PC Troubleshooting & Networking', 'LAB', 1, 3, 2, 3, 3, 3, 2, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (202, 'CAP 1', 'Capstone Project 1', 'LEC', 3, 4, 2, 2, 4, 3, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (203, 'IT 114', 'Networking 2', 'LEC', 2, 4, 1, 2, 4, 3, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (205, 'ProE 7', 'Human Computer Interaction 2', 'LEC', 2, 4, 1, 2, 4, 3, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (207, 'IC 7', 'Introduction to Web API and Socket Development', 'LEC', 2, 4, 1, 2, 4, 3, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (208, 'IC 7', 'Introduction to Web API and Socket Development', 'LAB', 1, 3, 1, 3, 3, 3, 2, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (188, 'Prof.3 E', 'Integrative Programming Technologies 2', 'LAB', 1, 3, 2, 3, 3, 3, 1, 1, 't', 'f');
INSERT INTO "public"."subjects" VALUES (81, 'CC 101', ' Introduction to Computing', 'LEC', 2, 4, 2, 2, 4, 1, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (82, 'CC 101', ' Introduction to Computing', 'LAB', 1, 3, 2, 3, 3, 1, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (83, 'CC 102', 'Fundamentals of Programming', 'LEC', 2, 4, 2, 2, 4, 1, 1, 3, 't', 'f');
INSERT INTO "public"."subjects" VALUES (7, 'CC 102', 'Fundamentals of Programming', 'LEC', 2, 4, 0, 2, 4, 1, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (86, 'PE 11', 'Movement Enhancement (ME)', 'LEC', 2, 4, 2, 2, 4, 1, 1, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (8, 'CC 102', 'Fundamentals of Programming', 'LAB', 1, 3, 0, 3, 3, 1, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (85, 'GEE - RVA', 'Reading Visual Art', 'LEC', 3, 4, 1, 2, 4, 1, 1, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (224, 'PE 12', 'Fitness Exercise (FE)', 'LEC', 2, 1, 0, 2, 4, 1, 2, 3, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (9, 'GE - US', 'Understanding the Self', 'LEC', 3, 4, 0, 2, 4, 1, 1, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (10, 'PE 11', 'Movement Enhancement (ME)', 'LEC', 2, 4, 0, 2, 4, 1, 1, 4, 'f', 'f');
INSERT INTO "public"."subjects" VALUES (48, 'CC 106', 'Application Development & Emerging Technology', 'LAB', 1, 3, 1, 3, 3, 3, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (49, 'CC 106', 'Application Development & Emerging Technology', 'LEC', 2, 4, 0, 2, 4, 3, 1, 4, 't', 'f');
INSERT INTO "public"."subjects" VALUES (50, 'CS Prof Elect 5', 'Data Mining', 'LEC', 3, 4, 0, 2, 4, 3, 1, 4, 't', 'f');

-- ----------------------------
-- Table structure for swap_requests
-- ----------------------------
DROP TABLE IF EXISTS "public"."swap_requests";
CREATE TABLE "public"."swap_requests" (
  "id" int4 NOT NULL DEFAULT nextval('swap_requests_id_seq'::regclass),
  "requester_schedule_id" int4 NOT NULL,
  "target_schedule_id" int4 NOT NULL,
  "requester_id" int4 NOT NULL,
  "target_id" int4 NOT NULL,
  "reason" text COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "rejection_reason" text COLLATE "pg_catalog"."default",
  "created_at" timestamp(6),
  "responded_at" timestamp(6)
)
;

-- ----------------------------
-- Records of swap_requests
-- ----------------------------

-- ----------------------------
-- Table structure for time_blocks
-- ----------------------------
DROP TABLE IF EXISTS "public"."time_blocks";
CREATE TABLE "public"."time_blocks" (
  "block_id" int4 NOT NULL,
  "day_id" int4 NOT NULL,
  "label" varchar(80) COLLATE "pg_catalog"."default",
  "start_time" time(6) NOT NULL,
  "end_time" time(6) NOT NULL,
  "start_min" int4 NOT NULL,
  "end_min" int4 NOT NULL,
  "is_lab" bool NOT NULL DEFAULT false
)
;

-- ----------------------------
-- Records of time_blocks
-- ----------------------------
INSERT INTO "public"."time_blocks" VALUES (101, 1, 'M 7:00–8:30', '07:00:00', '08:30:00', 420, 510, 'f');
INSERT INTO "public"."time_blocks" VALUES (102, 1, 'M 7:30–8:30', '07:30:00', '08:30:00', 450, 510, 'f');
INSERT INTO "public"."time_blocks" VALUES (103, 1, 'M 7:30–9:00 LAB', '07:30:00', '09:00:00', 450, 540, 't');
INSERT INTO "public"."time_blocks" VALUES (104, 1, 'M 8:00–9:00', '08:00:00', '09:00:00', 480, 540, 'f');
INSERT INTO "public"."time_blocks" VALUES (105, 1, 'M 8:30–10:00', '08:30:00', '10:00:00', 510, 600, 'f');
INSERT INTO "public"."time_blocks" VALUES (106, 1, 'M 9:00–10:00', '09:00:00', '10:00:00', 540, 600, 'f');
INSERT INTO "public"."time_blocks" VALUES (107, 1, 'M 9:00–10:30 LAB', '09:00:00', '10:30:00', 540, 630, 't');
INSERT INTO "public"."time_blocks" VALUES (108, 1, 'M 9:00–12:00', '09:00:00', '12:00:00', 540, 720, 'f');
INSERT INTO "public"."time_blocks" VALUES (109, 1, 'M 10:30–11:30', '10:30:00', '11:30:00', 630, 690, 'f');
INSERT INTO "public"."time_blocks" VALUES (110, 1, 'M 10:30–12:00 LAB', '10:30:00', '12:00:00', 630, 720, 't');
INSERT INTO "public"."time_blocks" VALUES (111, 1, 'M 11:00–12:00', '11:00:00', '12:00:00', 660, 720, 'f');
INSERT INTO "public"."time_blocks" VALUES (112, 1, 'M 13:00–14:00', '13:00:00', '14:00:00', 780, 840, 'f');
INSERT INTO "public"."time_blocks" VALUES (113, 1, 'M 13:00–14:30', '13:00:00', '14:30:00', 780, 870, 'f');
INSERT INTO "public"."time_blocks" VALUES (114, 1, 'M 13:00–15:00', '13:00:00', '15:00:00', 780, 900, 'f');
INSERT INTO "public"."time_blocks" VALUES (115, 1, 'M 14:00–15:00', '14:00:00', '15:00:00', 840, 900, 'f');
INSERT INTO "public"."time_blocks" VALUES (116, 1, 'M 14:30–16:00 LAB', '14:30:00', '16:00:00', 870, 960, 't');
INSERT INTO "public"."time_blocks" VALUES (117, 1, 'M 15:00–17:00', '15:00:00', '17:00:00', 900, 1020, 'f');
INSERT INTO "public"."time_blocks" VALUES (118, 1, 'M 16:00–17:30 LAB', '16:00:00', '17:30:00', 960, 1050, 't');
INSERT INTO "public"."time_blocks" VALUES (119, 1, 'M 17:30–19:00', '17:30:00', '19:00:00', 1050, 1140, 'f');
INSERT INTO "public"."time_blocks" VALUES (201, 2, 'T 7:00–8:30', '07:00:00', '08:30:00', 420, 510, 'f');
INSERT INTO "public"."time_blocks" VALUES (202, 2, 'T 7:30–8:30', '07:30:00', '08:30:00', 450, 510, 'f');
INSERT INTO "public"."time_blocks" VALUES (203, 2, 'T 7:30–9:00 LAB', '07:30:00', '09:00:00', 450, 540, 't');
INSERT INTO "public"."time_blocks" VALUES (204, 2, 'T 8:00–9:00', '08:00:00', '09:00:00', 480, 540, 'f');
INSERT INTO "public"."time_blocks" VALUES (205, 2, 'T 8:30–10:00', '08:30:00', '10:00:00', 510, 600, 'f');
INSERT INTO "public"."time_blocks" VALUES (206, 2, 'T 9:00–10:00', '09:00:00', '10:00:00', 540, 600, 'f');
INSERT INTO "public"."time_blocks" VALUES (207, 2, 'T 9:00–10:30 LAB', '09:00:00', '10:30:00', 540, 630, 't');
INSERT INTO "public"."time_blocks" VALUES (208, 2, 'T 9:00–12:00', '09:00:00', '12:00:00', 540, 720, 'f');
INSERT INTO "public"."time_blocks" VALUES (209, 2, 'T 10:30–11:30', '10:30:00', '11:30:00', 630, 690, 'f');
INSERT INTO "public"."time_blocks" VALUES (210, 2, 'T 10:30–12:00 LAB', '10:30:00', '12:00:00', 630, 720, 't');
INSERT INTO "public"."time_blocks" VALUES (211, 2, 'T 11:00–12:00', '11:00:00', '12:00:00', 660, 720, 'f');
INSERT INTO "public"."time_blocks" VALUES (212, 2, 'T 13:00–14:00', '13:00:00', '14:00:00', 780, 840, 'f');
INSERT INTO "public"."time_blocks" VALUES (213, 2, 'T 13:00–14:30', '13:00:00', '14:30:00', 780, 870, 'f');
INSERT INTO "public"."time_blocks" VALUES (214, 2, 'T 13:00–15:00', '13:00:00', '15:00:00', 780, 900, 'f');
INSERT INTO "public"."time_blocks" VALUES (215, 2, 'T 14:00–15:00', '14:00:00', '15:00:00', 840, 900, 'f');
INSERT INTO "public"."time_blocks" VALUES (216, 2, 'T 14:30–16:00 LAB', '14:30:00', '16:00:00', 870, 960, 't');
INSERT INTO "public"."time_blocks" VALUES (217, 2, 'T 15:00–17:00', '15:00:00', '17:00:00', 900, 1020, 'f');
INSERT INTO "public"."time_blocks" VALUES (218, 2, 'T 16:00–17:30 LAB', '16:00:00', '17:30:00', 960, 1050, 't');
INSERT INTO "public"."time_blocks" VALUES (219, 2, 'T 17:30–19:00', '17:30:00', '19:00:00', 1050, 1140, 'f');
INSERT INTO "public"."time_blocks" VALUES (301, 3, 'W 7:00–8:30', '07:00:00', '08:30:00', 420, 510, 'f');
INSERT INTO "public"."time_blocks" VALUES (302, 3, 'W 7:30–8:30', '07:30:00', '08:30:00', 450, 510, 'f');
INSERT INTO "public"."time_blocks" VALUES (303, 3, 'W 7:30–9:00 LAB', '07:30:00', '09:00:00', 450, 540, 't');
INSERT INTO "public"."time_blocks" VALUES (304, 3, 'W 8:00–9:00', '08:00:00', '09:00:00', 480, 540, 'f');
INSERT INTO "public"."time_blocks" VALUES (305, 3, 'W 8:30–10:00', '08:30:00', '10:00:00', 510, 600, 'f');
INSERT INTO "public"."time_blocks" VALUES (306, 3, 'W 9:00–10:00', '09:00:00', '10:00:00', 540, 600, 'f');
INSERT INTO "public"."time_blocks" VALUES (307, 3, 'W 9:00–10:30 LAB', '09:00:00', '10:30:00', 540, 630, 't');
INSERT INTO "public"."time_blocks" VALUES (308, 3, 'W 9:00–12:00', '09:00:00', '12:00:00', 540, 720, 'f');
INSERT INTO "public"."time_blocks" VALUES (309, 3, 'W 10:30–11:30', '10:30:00', '11:30:00', 630, 690, 'f');
INSERT INTO "public"."time_blocks" VALUES (310, 3, 'W 10:30–12:00 LAB', '10:30:00', '12:00:00', 630, 720, 't');
INSERT INTO "public"."time_blocks" VALUES (311, 3, 'W 11:00–12:00', '11:00:00', '12:00:00', 660, 720, 'f');
INSERT INTO "public"."time_blocks" VALUES (312, 3, 'W 13:00–14:00', '13:00:00', '14:00:00', 780, 840, 'f');
INSERT INTO "public"."time_blocks" VALUES (313, 3, 'W 13:00–14:30', '13:00:00', '14:30:00', 780, 870, 'f');
INSERT INTO "public"."time_blocks" VALUES (314, 3, 'W 13:00–15:00', '13:00:00', '15:00:00', 780, 900, 'f');
INSERT INTO "public"."time_blocks" VALUES (315, 3, 'W 14:00–15:00', '14:00:00', '15:00:00', 840, 900, 'f');
INSERT INTO "public"."time_blocks" VALUES (316, 3, 'W 14:30–16:00 LAB', '14:30:00', '16:00:00', 870, 960, 't');
INSERT INTO "public"."time_blocks" VALUES (317, 3, 'W 15:00–17:00', '15:00:00', '17:00:00', 900, 1020, 'f');
INSERT INTO "public"."time_blocks" VALUES (318, 3, 'W 16:00–17:30 LAB', '16:00:00', '17:30:00', 960, 1050, 't');
INSERT INTO "public"."time_blocks" VALUES (319, 3, 'W 17:30–19:00', '17:30:00', '19:00:00', 1050, 1140, 'f');
INSERT INTO "public"."time_blocks" VALUES (401, 4, 'TH 7:00–8:30', '07:00:00', '08:30:00', 420, 510, 'f');
INSERT INTO "public"."time_blocks" VALUES (402, 4, 'TH 7:30–8:30', '07:30:00', '08:30:00', 450, 510, 'f');
INSERT INTO "public"."time_blocks" VALUES (403, 4, 'TH 7:30–9:00 LAB', '07:30:00', '09:00:00', 450, 540, 't');
INSERT INTO "public"."time_blocks" VALUES (404, 4, 'TH 8:00–9:00', '08:00:00', '09:00:00', 480, 540, 'f');
INSERT INTO "public"."time_blocks" VALUES (405, 4, 'TH 8:30–10:00', '08:30:00', '10:00:00', 510, 600, 'f');
INSERT INTO "public"."time_blocks" VALUES (406, 4, 'TH 9:00–10:00', '09:00:00', '10:00:00', 540, 600, 'f');
INSERT INTO "public"."time_blocks" VALUES (407, 4, 'TH 9:00–10:30 LAB', '09:00:00', '10:30:00', 540, 630, 't');
INSERT INTO "public"."time_blocks" VALUES (408, 4, 'TH 9:00–12:00', '09:00:00', '12:00:00', 540, 720, 'f');
INSERT INTO "public"."time_blocks" VALUES (409, 4, 'TH 10:30–11:30', '10:30:00', '11:30:00', 630, 690, 'f');
INSERT INTO "public"."time_blocks" VALUES (410, 4, 'TH 10:30–12:00 LAB', '10:30:00', '12:00:00', 630, 720, 't');
INSERT INTO "public"."time_blocks" VALUES (411, 4, 'TH 11:00–12:00', '11:00:00', '12:00:00', 660, 720, 'f');
INSERT INTO "public"."time_blocks" VALUES (412, 4, 'TH 13:00–14:00', '13:00:00', '14:00:00', 780, 840, 'f');
INSERT INTO "public"."time_blocks" VALUES (413, 4, 'TH 13:00–14:30', '13:00:00', '14:30:00', 780, 870, 'f');
INSERT INTO "public"."time_blocks" VALUES (414, 4, 'TH 13:00–15:00', '13:00:00', '15:00:00', 780, 900, 'f');
INSERT INTO "public"."time_blocks" VALUES (415, 4, 'TH 14:00–15:00', '14:00:00', '15:00:00', 840, 900, 'f');
INSERT INTO "public"."time_blocks" VALUES (416, 4, 'TH 14:30–16:00 LAB', '14:30:00', '16:00:00', 870, 960, 't');
INSERT INTO "public"."time_blocks" VALUES (417, 4, 'TH 15:00–17:00', '15:00:00', '17:00:00', 900, 1020, 'f');
INSERT INTO "public"."time_blocks" VALUES (418, 4, 'TH 16:00–17:30 LAB', '16:00:00', '17:30:00', 960, 1050, 't');
INSERT INTO "public"."time_blocks" VALUES (419, 4, 'TH 17:30–19:00', '17:30:00', '19:00:00', 1050, 1140, 'f');
INSERT INTO "public"."time_blocks" VALUES (501, 5, 'F 7:00–8:30', '07:00:00', '08:30:00', 420, 510, 'f');
INSERT INTO "public"."time_blocks" VALUES (502, 5, 'F 7:30–8:30', '07:30:00', '08:30:00', 450, 510, 'f');
INSERT INTO "public"."time_blocks" VALUES (503, 5, 'F 7:30–9:00 LAB', '07:30:00', '09:00:00', 450, 540, 't');
INSERT INTO "public"."time_blocks" VALUES (504, 5, 'F 8:00–9:00', '08:00:00', '09:00:00', 480, 540, 'f');
INSERT INTO "public"."time_blocks" VALUES (505, 5, 'F 8:30–10:00', '08:30:00', '10:00:00', 510, 600, 'f');
INSERT INTO "public"."time_blocks" VALUES (506, 5, 'F 9:00–10:00', '09:00:00', '10:00:00', 540, 600, 'f');
INSERT INTO "public"."time_blocks" VALUES (507, 5, 'F 9:00–10:30 LAB', '09:00:00', '10:30:00', 540, 630, 't');
INSERT INTO "public"."time_blocks" VALUES (508, 5, 'F 9:00–12:00', '09:00:00', '12:00:00', 540, 720, 'f');
INSERT INTO "public"."time_blocks" VALUES (509, 5, 'F 10:30–11:30', '10:30:00', '11:30:00', 630, 690, 'f');
INSERT INTO "public"."time_blocks" VALUES (510, 5, 'F 10:30–12:00 LAB', '10:30:00', '12:00:00', 630, 720, 't');
INSERT INTO "public"."time_blocks" VALUES (511, 5, 'F 11:00–12:00', '11:00:00', '12:00:00', 660, 720, 'f');
INSERT INTO "public"."time_blocks" VALUES (512, 5, 'F 13:00–14:00', '13:00:00', '14:00:00', 780, 840, 'f');
INSERT INTO "public"."time_blocks" VALUES (513, 5, 'F 13:00–14:30', '13:00:00', '14:30:00', 780, 870, 'f');
INSERT INTO "public"."time_blocks" VALUES (514, 5, 'F 13:00–15:00', '13:00:00', '15:00:00', 780, 900, 'f');
INSERT INTO "public"."time_blocks" VALUES (515, 5, 'F 14:00–15:00', '14:00:00', '15:00:00', 840, 900, 'f');
INSERT INTO "public"."time_blocks" VALUES (516, 5, 'F 14:30–16:00 LAB', '14:30:00', '16:00:00', 870, 960, 't');
INSERT INTO "public"."time_blocks" VALUES (517, 5, 'F 15:00–17:00', '15:00:00', '17:00:00', 900, 1020, 'f');
INSERT INTO "public"."time_blocks" VALUES (518, 5, 'F 16:00–17:30 LAB', '16:00:00', '17:30:00', 960, 1050, 't');
INSERT INTO "public"."time_blocks" VALUES (519, 5, 'F 17:30–19:00', '17:30:00', '19:00:00', 1050, 1140, 'f');

-- ----------------------------
-- Table structure for timeslots
-- ----------------------------
DROP TABLE IF EXISTS "public"."timeslots";
CREATE TABLE "public"."timeslots" (
  "id" int4 NOT NULL DEFAULT nextval('timeslots_id_seq'::regclass),
  "label" varchar(50) COLLATE "pg_catalog"."default",
  "day" int4 NOT NULL,
  "start_min" int4 NOT NULL,
  "end_min" int4 NOT NULL,
  "is_lab" bool DEFAULT false
)
;

-- ----------------------------
-- Records of timeslots
-- ----------------------------
INSERT INTO "public"."timeslots" VALUES (1, 'M 07:00', 1, -1036120315, -1036120225, 'f');
INSERT INTO "public"."timeslots" VALUES (2, 'M 07:30 LAB', 1, -1036120285, -1036120195, 't');
INSERT INTO "public"."timeslots" VALUES (3, 'M 07:30', 1, -1036120285, -1036120225, 'f');
INSERT INTO "public"."timeslots" VALUES (4, 'M 08:00', 1, -1036120255, -1036120195, 'f');
INSERT INTO "public"."timeslots" VALUES (5, 'M 08:30', 1, -1036120225, -1036120135, 'f');
INSERT INTO "public"."timeslots" VALUES (6, 'M 09:00', 1, -1036120195, -1036120135, 'f');
INSERT INTO "public"."timeslots" VALUES (7, 'M 09:00 LAB', 1, -1036120195, -1036120105, 't');
INSERT INTO "public"."timeslots" VALUES (8, 'M 09:00', 1, -1036120195, -1036120015, 'f');
INSERT INTO "public"."timeslots" VALUES (9, 'M 10:30 LAB', 1, -1036120105, -1036120015, 't');
INSERT INTO "public"."timeslots" VALUES (10, 'M 10:30', 1, -1036120105, -1036120045, 'f');
INSERT INTO "public"."timeslots" VALUES (11, 'M 11:00', 1, -1036120075, -1036120015, 'f');
INSERT INTO "public"."timeslots" VALUES (12, 'M 01:00', 1, -1036119955, -1036119835, 'f');
INSERT INTO "public"."timeslots" VALUES (13, 'M 01:00', 1, -1036119955, -1036119895, 'f');
INSERT INTO "public"."timeslots" VALUES (14, 'M 01:00', 1, -1036119955, -1036119865, 'f');
INSERT INTO "public"."timeslots" VALUES (15, 'M 02:00', 1, -1036119895, -1036119835, 'f');
INSERT INTO "public"."timeslots" VALUES (16, 'M 02:30 LAB', 1, -1036119865, -1036119775, 't');
INSERT INTO "public"."timeslots" VALUES (17, 'M 03:00', 1, -1036119835, -1036119715, 'f');
INSERT INTO "public"."timeslots" VALUES (18, 'M 04:00 LAB', 1, -1036119775, -1036119685, 't');
INSERT INTO "public"."timeslots" VALUES (19, 'M 05:30', 1, -1036119685, -1036119595, 'f');
INSERT INTO "public"."timeslots" VALUES (20, 'T 07:00', 2, -1036120315, -1036120225, 'f');
INSERT INTO "public"."timeslots" VALUES (21, 'T 07:30 LAB', 2, -1036120285, -1036120195, 't');
INSERT INTO "public"."timeslots" VALUES (22, 'T 07:30', 2, -1036120285, -1036120225, 'f');
INSERT INTO "public"."timeslots" VALUES (23, 'T 08:00', 2, -1036120255, -1036120195, 'f');
INSERT INTO "public"."timeslots" VALUES (24, 'T 08:30', 2, -1036120225, -1036120135, 'f');
INSERT INTO "public"."timeslots" VALUES (25, 'T 09:00', 2, -1036120195, -1036120015, 'f');
INSERT INTO "public"."timeslots" VALUES (26, 'T 09:00 LAB', 2, -1036120195, -1036120105, 't');
INSERT INTO "public"."timeslots" VALUES (27, 'T 09:00', 2, -1036120195, -1036120135, 'f');
INSERT INTO "public"."timeslots" VALUES (28, 'T 10:30 LAB', 2, -1036120105, -1036120015, 't');
INSERT INTO "public"."timeslots" VALUES (29, 'T 10:30', 2, -1036120105, -1036120045, 'f');
INSERT INTO "public"."timeslots" VALUES (30, 'T 11:00', 2, -1036120075, -1036120015, 'f');
INSERT INTO "public"."timeslots" VALUES (31, 'T 01:00', 2, -1036119955, -1036119835, 'f');
INSERT INTO "public"."timeslots" VALUES (32, 'T 01:00', 2, -1036119955, -1036119865, 'f');
INSERT INTO "public"."timeslots" VALUES (33, 'T 01:00', 2, -1036119955, -1036119895, 'f');
INSERT INTO "public"."timeslots" VALUES (34, 'T 02:00', 2, -1036119895, -1036119835, 'f');
INSERT INTO "public"."timeslots" VALUES (35, 'T 02:30 LAB', 2, -1036119865, -1036119775, 't');
INSERT INTO "public"."timeslots" VALUES (36, 'T 03:00', 2, -1036119835, -1036119715, 'f');
INSERT INTO "public"."timeslots" VALUES (37, 'T 04:00 LAB', 2, -1036119775, -1036119685, 't');
INSERT INTO "public"."timeslots" VALUES (38, 'T 05:30', 2, -1036119685, -1036119595, 'f');
INSERT INTO "public"."timeslots" VALUES (39, 'W 07:00', 3, -1036120315, -1036120225, 'f');
INSERT INTO "public"."timeslots" VALUES (40, 'W 07:30', 3, -1036120285, -1036120225, 'f');
INSERT INTO "public"."timeslots" VALUES (41, 'W 07:30 LAB', 3, -1036120285, -1036120195, 't');
INSERT INTO "public"."timeslots" VALUES (42, 'W 08:00', 3, -1036120255, -1036120195, 'f');
INSERT INTO "public"."timeslots" VALUES (43, 'W 08:30', 3, -1036120225, -1036120135, 'f');
INSERT INTO "public"."timeslots" VALUES (44, 'W 09:00 LAB', 3, -1036120195, -1036120105, 't');
INSERT INTO "public"."timeslots" VALUES (45, 'W 09:00', 3, -1036120195, -1036120015, 'f');
INSERT INTO "public"."timeslots" VALUES (46, 'W 09:00', 3, -1036120195, -1036120135, 'f');
INSERT INTO "public"."timeslots" VALUES (47, 'W 10:30 LAB', 3, -1036120105, -1036120015, 't');
INSERT INTO "public"."timeslots" VALUES (48, 'W 10:30', 3, -1036120105, -1036120045, 'f');
INSERT INTO "public"."timeslots" VALUES (49, 'W 11:00', 3, -1036120075, -1036120015, 'f');
INSERT INTO "public"."timeslots" VALUES (50, 'W 01:00', 3, -1036119955, -1036119835, 'f');
INSERT INTO "public"."timeslots" VALUES (51, 'W 01:00', 3, -1036119955, -1036119895, 'f');
INSERT INTO "public"."timeslots" VALUES (52, 'W 01:00', 3, -1036119955, -1036119865, 'f');
INSERT INTO "public"."timeslots" VALUES (53, 'W 02:00', 3, -1036119895, -1036119835, 'f');
INSERT INTO "public"."timeslots" VALUES (54, 'W 02:30 LAB', 3, -1036119865, -1036119775, 't');
INSERT INTO "public"."timeslots" VALUES (55, 'W 03:00', 3, -1036119835, -1036119715, 'f');
INSERT INTO "public"."timeslots" VALUES (56, 'W 04:00 LAB', 3, -1036119775, -1036119685, 't');
INSERT INTO "public"."timeslots" VALUES (57, 'W 05:30', 3, -1036119685, -1036119595, 'f');
INSERT INTO "public"."timeslots" VALUES (58, 'TH 07:00', 4, -1036120315, -1036120225, 'f');
INSERT INTO "public"."timeslots" VALUES (59, 'TH 07:30', 4, -1036120285, -1036120225, 'f');
INSERT INTO "public"."timeslots" VALUES (60, 'TH 07:30 LAB', 4, -1036120285, -1036120195, 't');
INSERT INTO "public"."timeslots" VALUES (61, 'TH 08:00', 4, -1036120255, -1036120195, 'f');
INSERT INTO "public"."timeslots" VALUES (62, 'TH 08:30', 4, -1036120225, -1036120135, 'f');
INSERT INTO "public"."timeslots" VALUES (63, 'TH 09:00', 4, -1036120195, -1036120135, 'f');
INSERT INTO "public"."timeslots" VALUES (64, 'TH 09:00', 4, -1036120195, -1036120015, 'f');
INSERT INTO "public"."timeslots" VALUES (65, 'TH 09:00 LAB', 4, -1036120195, -1036120105, 't');
INSERT INTO "public"."timeslots" VALUES (66, 'TH 10:30 LAB', 4, -1036120105, -1036120015, 't');
INSERT INTO "public"."timeslots" VALUES (67, 'TH 10:30', 4, -1036120105, -1036120045, 'f');
INSERT INTO "public"."timeslots" VALUES (68, 'TH 11:00', 4, -1036120075, -1036120015, 'f');
INSERT INTO "public"."timeslots" VALUES (69, 'TH 01:00', 4, -1036119955, -1036119835, 'f');
INSERT INTO "public"."timeslots" VALUES (70, 'TH 01:00', 4, -1036119955, -1036119895, 'f');
INSERT INTO "public"."timeslots" VALUES (71, 'TH 01:00', 4, -1036119955, -1036119865, 'f');
INSERT INTO "public"."timeslots" VALUES (72, 'TH 02:00', 4, -1036119895, -1036119835, 'f');
INSERT INTO "public"."timeslots" VALUES (73, 'TH 02:30 LAB', 4, -1036119865, -1036119775, 't');
INSERT INTO "public"."timeslots" VALUES (74, 'TH 03:00', 4, -1036119835, -1036119715, 'f');
INSERT INTO "public"."timeslots" VALUES (75, 'TH 04:00 LAB', 4, -1036119775, -1036119685, 't');
INSERT INTO "public"."timeslots" VALUES (76, 'TH 05:30', 4, -1036119685, -1036119595, 'f');
INSERT INTO "public"."timeslots" VALUES (77, 'F 07:00', 5, -1036120315, -1036120225, 'f');
INSERT INTO "public"."timeslots" VALUES (78, 'F 07:30', 5, -1036120285, -1036120225, 'f');
INSERT INTO "public"."timeslots" VALUES (79, 'F 07:30 LAB', 5, -1036120285, -1036120195, 't');
INSERT INTO "public"."timeslots" VALUES (80, 'F 08:00', 5, -1036120255, -1036120195, 'f');
INSERT INTO "public"."timeslots" VALUES (81, 'F 08:30', 5, -1036120225, -1036120135, 'f');
INSERT INTO "public"."timeslots" VALUES (82, 'F 09:00', 5, -1036120195, -1036120015, 'f');
INSERT INTO "public"."timeslots" VALUES (83, 'F 09:00', 5, -1036120195, -1036120135, 'f');
INSERT INTO "public"."timeslots" VALUES (84, 'F 09:00 LAB', 5, -1036120195, -1036120105, 't');
INSERT INTO "public"."timeslots" VALUES (85, 'F 10:30', 5, -1036120105, -1036120045, 'f');
INSERT INTO "public"."timeslots" VALUES (86, 'F 10:30 LAB', 5, -1036120105, -1036120015, 't');
INSERT INTO "public"."timeslots" VALUES (87, 'F 11:00', 5, -1036120075, -1036120015, 'f');
INSERT INTO "public"."timeslots" VALUES (88, 'F 01:00', 5, -1036119955, -1036119895, 'f');
INSERT INTO "public"."timeslots" VALUES (89, 'F 01:00', 5, -1036119955, -1036119835, 'f');
INSERT INTO "public"."timeslots" VALUES (90, 'F 01:00', 5, -1036119955, -1036119865, 'f');
INSERT INTO "public"."timeslots" VALUES (91, 'F 02:00', 5, -1036119895, -1036119835, 'f');
INSERT INTO "public"."timeslots" VALUES (92, 'F 02:30 LAB', 5, -1036119865, -1036119775, 't');
INSERT INTO "public"."timeslots" VALUES (93, 'F 03:00', 5, -1036119835, -1036119715, 'f');
INSERT INTO "public"."timeslots" VALUES (94, 'F 04:00 LAB', 5, -1036119775, -1036119685, 't');
INSERT INTO "public"."timeslots" VALUES (95, 'F 05:30', 5, -1036119685, -1036119595, 'f');

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS "public"."users";
CREATE TABLE "public"."users" (
  "id" int4 NOT NULL DEFAULT nextval('users_id_seq'::regclass),
  "username" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "password_hash" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "role" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "instructor_id" int4
)
;

-- ----------------------------
-- Records of users
-- ----------------------------
INSERT INTO "public"."users" VALUES (1, 'registrar', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'registrar', NULL);
INSERT INTO "public"."users" VALUES (2, 'instructor', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 1);
INSERT INTO "public"."users" VALUES (3, 'admin', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'admin', NULL);
INSERT INTO "public"."users" VALUES (7, 'allan.patrick', '17ce7046af8abe65c85025aa7d8879e417c269fcb61af1197f56cddd04a4bc26', 'instructor', 35);
INSERT INTO "public"."users" VALUES (8, 'fdad', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 4);
INSERT INTO "public"."users" VALUES (9, 'jdoe', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 3);
INSERT INTO "public"."users" VALUES (10, 'msantos', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 2);
INSERT INTO "public"."users" VALUES (11, 'jcruz', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 5);
INSERT INTO "public"."users" VALUES (12, 'abinibirocha', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 6);
INSERT INTO "public"."users" VALUES (13, 'ldizon', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 7);
INSERT INTO "public"."users" VALUES (14, 'cong', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 8);
INSERT INTO "public"."users" VALUES (15, 'erivera', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 9);
INSERT INTO "public"."users" VALUES (16, 'alim', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 10);
INSERT INTO "public"."users" VALUES (17, 'rmanalo', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 11);
INSERT INTO "public"."users" VALUES (18, 'kramos', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 12);
INSERT INTO "public"."users" VALUES (19, 'apascual', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 13);
INSERT INTO "public"."users" VALUES (20, 'knavarro', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 14);
INSERT INTO "public"."users" VALUES (21, 'lgonzales', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 16);
INSERT INTO "public"."users" VALUES (22, 'jflores', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 15);
INSERT INTO "public"."users" VALUES (23, 'ealcantara', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 17);
INSERT INTO "public"."users" VALUES (24, 'jcastillo', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 18);
INSERT INTO "public"."users" VALUES (25, 'avillanueva', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 20);
INSERT INTO "public"."users" VALUES (26, 'kramirez', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 19);
INSERT INTO "public"."users" VALUES (27, 'avaldez', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 21);
INSERT INTO "public"."users" VALUES (28, 'fsoriano', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 22);
INSERT INTO "public"."users" VALUES (29, 'bsarte', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 23);
INSERT INTO "public"."users" VALUES (30, 'fordoez', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 24);
INSERT INTO "public"."users" VALUES (31, 'hcaete', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 25);
INSERT INTO "public"."users" VALUES (32, 'gpanganiban', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 26);
INSERT INTO "public"."users" VALUES (33, 'jvelasco', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 27);
INSERT INTO "public"."users" VALUES (34, 'nestrella', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 28);
INSERT INTO "public"."users" VALUES (35, 'vocampo', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 29);
INSERT INTO "public"."users" VALUES (36, 'zsalazar', '03ac674216f3e15c761ee1a5e255f067953623c8b388b4459e13f978d7c846f4', 'instructor', 30);
INSERT INTO "public"."users" VALUES (37, 'test', 'cf80cd8aed482d5d1527d7dc72fceff84e6326592848447d2dc0b0e87dfc9a90', 'instructor', 36);

-- ----------------------------
-- Function structure for _navicat_temp_stored_proc
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."_navicat_temp_stored_proc"("p_course_id" int4, "p_college_id" int4, "p_cluster_id" int4, "p_subject_ids" _int4, "p_year_level" int4, "p_semester" int4);
CREATE OR REPLACE FUNCTION "public"."_navicat_temp_stored_proc"("p_course_id" int4=NULL::integer, "p_college_id" int4=NULL::integer, "p_cluster_id" int4=NULL::integer, "p_subject_ids" _int4=NULL::integer[], "p_year_level" int4=NULL::integer, "p_semester" int4=NULL::integer)
  RETURNS TABLE("subject_id" int4) AS $BODY$
BEGIN
    RETURN QUERY
    SELECT s.id
    FROM subjects s
    LEFT JOIN courses c ON s.course_id = c.id
    WHERE (p_course_id IS NULL OR s.course_id = p_course_id)
      AND (p_college_id IS NULL OR c.college_id = p_college_id)
      AND (p_cluster_id IS NULL OR s.cluster = p_cluster_id)
      AND (p_subject_ids IS NULL OR s.id = ANY(p_subject_ids))
      AND (p_year_level IS NULL OR s.year_level = p_year_level)
      AND (p_semester IS NULL OR s.semester = p_semester)
    ORDER BY s.cluster, s.course_id, s.year_level, s.semester, s.code;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;

-- ----------------------------
-- Function structure for _navicat_temp_stored_proc
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."_navicat_temp_stored_proc"("p_course_id" int4, "p_college_id" int4, "p_cluster_id" int4, "p_subject_ids" _text, "p_year_level" int4, "p_semester" int4);
CREATE OR REPLACE FUNCTION "public"."_navicat_temp_stored_proc"("p_course_id" int4, "p_college_id" int4, "p_cluster_id" int4, "p_subject_ids" _text, "p_year_level" int4, "p_semester" int4)
  RETURNS TABLE("subject_id" int4) AS $BODY$
BEGIN
    RETURN QUERY
    SELECT s.id
    FROM subject AS s
    WHERE (p_course_id IS NULL OR s.course_id = p_course_id)
      AND (p_college_id IS NULL OR s.college_id = p_college_id)
      AND (p_cluster_id IS NULL OR s.cluster_id = p_cluster_id)
      AND (p_subject_ids IS NULL OR s.id::TEXT = ANY (p_subject_ids))
      AND (p_year_level IS NULL OR s.year_level = p_year_level)
      AND (p_semester IS NULL OR s.semester = p_semester);
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;

-- ----------------------------
-- Function structure for get_available_rooms
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."get_available_rooms"("p_type" text, "p_min_capacity" int4, "p_semester" int4, "p_year" int4, "p_day_id" int4, "p_time_label" text);
CREATE OR REPLACE FUNCTION "public"."get_available_rooms"("p_type" text, "p_min_capacity" int4=NULL::integer, "p_semester" int4=NULL::integer, "p_year" int4=NULL::integer, "p_day_id" int4=NULL::integer, "p_time_label" text=NULL::text)
  RETURNS TABLE("room_id" int4, "room_name" text, "room_type" text, "capacity" int4, "cluster" int4) AS $BODY$
BEGIN
    RETURN QUERY
    SELECT 
        r.id AS room_id,
        r.name::TEXT AS room_name,
        r.type::TEXT AS room_type,
        r.capacity,
        r.cluster
    FROM rooms r
    WHERE r.type = p_type
      AND (p_min_capacity IS NULL OR r.capacity >= p_min_capacity)
      AND (
          -- If checking availability for specific time slot
          p_semester IS NULL OR p_day_id IS NULL OR p_time_label IS NULL OR
          NOT EXISTS (
              SELECT 1
              FROM schedules s
              WHERE s.room_id = r.id
                AND s.day_id = p_day_id
                AND s.time = p_time_label
                AND s.semester = p_semester
                AND (p_year IS NULL OR s.year = p_year)
          )
      )
    ORDER BY r.capacity DESC, r.id;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;

-- ----------------------------
-- Function structure for get_courses_by_college
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."get_courses_by_college"("p_college_id" int4);
CREATE OR REPLACE FUNCTION "public"."get_courses_by_college"("p_college_id" int4)
  RETURNS TABLE("course_id" int4, "code" text, "description" text, "college_id" int4) AS $BODY$
BEGIN
    RETURN QUERY
    SELECT 
        c.id AS course_id,
        c.code::TEXT,
        c.description::TEXT,
        c.college_id
    FROM courses c
    WHERE c.college_id = p_college_id
    ORDER BY c.code;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;

-- ----------------------------
-- Function structure for get_existing_bookings
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."get_existing_bookings"("p_semester" int4, "p_years" _int4, "p_exclude_course_id" int4, "p_exclude_years" _int4);
CREATE OR REPLACE FUNCTION "public"."get_existing_bookings"("p_semester" int4, "p_years" _int4=NULL::integer[], "p_exclude_course_id" int4=NULL::integer, "p_exclude_years" _int4=NULL::integer[])
  RETURNS TABLE("booking_type" text, "resource_id" int4, "resource_name" text, "day_id" int4, "time_label" text) AS $BODY$
BEGIN
    RETURN QUERY
    -- Room bookings
    SELECT 
        'room'::TEXT AS booking_type,
        s.room_id AS resource_id,
        r.name::TEXT AS resource_name,
        s.day_id,
        s.time::TEXT AS time_label
    FROM schedules s
    INNER JOIN rooms r ON s.room_id = r.id
    WHERE s.semester = p_semester
      AND (p_years IS NULL OR s.year = ANY(p_years))
      -- Exclude only the specific course+year combination being rescheduled
      AND NOT (
          p_exclude_course_id IS NOT NULL
          AND s.course_id = p_exclude_course_id
          AND (p_exclude_years IS NULL OR s.year = ANY(p_exclude_years))
      )
      AND s.room_id IS NOT NULL
      AND s.day_id IS NOT NULL
      AND s.time IS NOT NULL
    
    UNION ALL
    
    -- Instructor bookings
    SELECT 
        'instructor'::TEXT AS booking_type,
        s.instructor_id AS resource_id,
        (i.first_name || ' ' || i.last_name)::TEXT AS resource_name,
        s.day_id,
        s.time::TEXT AS time_label
    FROM schedules s
    INNER JOIN instructors i ON s.instructor_id = i.id
    WHERE s.semester = p_semester
      AND (p_years IS NULL OR s.year = ANY(p_years))
      -- Exclude only the specific course+year combination being rescheduled
      AND NOT (
          p_exclude_course_id IS NOT NULL
          AND s.course_id = p_exclude_course_id
          AND (p_exclude_years IS NULL OR s.year = ANY(p_exclude_years))
      )
      AND s.instructor_id IS NOT NULL
      AND s.day_id IS NOT NULL
      AND s.time IS NOT NULL;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;

-- ----------------------------
-- Function structure for get_instructor_availability
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."get_instructor_availability"("instr_id" int4, "p_semester" int4, "p_year" int4);
CREATE OR REPLACE FUNCTION "public"."get_instructor_availability"("instr_id" int4, "p_semester" int4, "p_year" int4=NULL::integer)
  RETURNS TABLE("day_id" int4, "day_label" text, "time_label" text, "start_min" int4, "end_min" int4) AS $BODY$
BEGIN
    RETURN QUERY
    SELECT 
        d.id AS day_id,
        d.label::TEXT AS day_label,
        t.label::TEXT AS time_label,
        t.start_min,
        t.end_min
    FROM timeslots t
    INNER JOIN days d ON t.day = d.id
    WHERE NOT EXISTS (
        SELECT 1
        FROM schedules s
        WHERE s.instructor_id = instr_id
          AND s.day_id = d.id
          AND s.time = t.label
          AND s.semester = p_semester
          AND (p_year IS NULL OR s.year = p_year)
    )
    ORDER BY d.id, t.start_min;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;

-- ----------------------------
-- Function structure for get_instructor_eligibility
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."get_instructor_eligibility"("p_subject_id" int4);
CREATE OR REPLACE FUNCTION "public"."get_instructor_eligibility"("p_subject_id" int4)
  RETURNS TABLE("instructor_id" int4, "first_name" text, "last_name" text, "college_id" int4, "assignable_courses" text) AS $BODY$
DECLARE
    v_subject_code TEXT;
BEGIN
    -- Get subject code
    SELECT s.code
    INTO v_subject_code
    FROM subjects s
    WHERE s.id = p_subject_id;
    
    RETURN QUERY
    SELECT 
        i.id AS instructor_id,
        i.first_name::TEXT,
        i.last_name::TEXT,
        i.college_id,
        i.assignable_courses::TEXT
    FROM instructors i
    WHERE 
        -- Only active instructors
        i.is_active = true
        AND
        -- Strict match: subject code must be in assignable_courses
        i.assignable_courses IS NOT NULL 
        AND v_subject_code IS NOT NULL
        AND UPPER(REGEXP_REPLACE(TRIM(v_subject_code), '[^A-Z0-9]', '', 'g')) = ANY(
            SELECT UPPER(REGEXP_REPLACE(TRIM(unnest(string_to_array(i.assignable_courses, ','))), '[^A-Z0-9]', '', 'g'))
        )
    ORDER BY i.id;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;

-- ----------------------------
-- Function structure for get_room_eligibility
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."get_room_eligibility"("p_subject_id" int4, "p_min_capacity" int4);
CREATE OR REPLACE FUNCTION "public"."get_room_eligibility"("p_subject_id" int4, "p_min_capacity" int4=NULL::integer)
  RETURNS TABLE("room_id" int4, "room_name" text, "room_type" text, "capacity" int4, "cluster" int4) AS $BODY$
DECLARE
    v_subject_type TEXT;
BEGIN
    -- Get subject type
    SELECT s.type INTO v_subject_type
    FROM subjects s
    WHERE s.id = p_subject_id;
    
    RETURN QUERY
    SELECT 
        r.id AS room_id,
        r.name::TEXT AS room_name,
        r.type::TEXT AS room_type,
        r.capacity,
        r.cluster
    FROM rooms r
    WHERE r.type = v_subject_type
      AND (p_min_capacity IS NULL OR r.capacity >= p_min_capacity)
    ORDER BY r.capacity DESC, r.id;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;

-- ----------------------------
-- Function structure for get_schedules_for_course
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."get_schedules_for_course"("p_course_id" int4, "p_semester" int4, "p_year" int4, "p_instructor_id" int4);
CREATE OR REPLACE FUNCTION "public"."get_schedules_for_course"("p_course_id" int4, "p_semester" int4, "p_year" int4=NULL::integer, "p_instructor_id" int4=NULL::integer)
  RETURNS TABLE("schedule_id" int4, "subject_id" int4, "instructor_id" int4, "room_id" int4, "day_id" int4, "time_label" text, "course_id" int4, "year" int4, "semester" int4) AS $BODY$
BEGIN
    RETURN QUERY
    SELECT 
        s.id AS schedule_id,
        s.subject_id,
        s.instructor_id,
        s.room_id,
        s.day_id,
        s.time::TEXT AS time_label,
        s.course_id,
        s.year,
        s.semester
    FROM schedules s
    WHERE s.course_id = p_course_id
      AND s.semester = p_semester
      AND (p_year IS NULL OR s.year = p_year)
      AND (p_instructor_id IS NULL OR s.instructor_id = p_instructor_id)
    ORDER BY s.year NULLS LAST, s.day_id, s.time;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;

-- ----------------------------
-- Function structure for get_subjects_for_scheduling
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."get_subjects_for_scheduling"("p_course_id" int4, "p_college_id" int4, "p_cluster_id" int4, "p_subject_ids" _int4, "p_year_level" int4, "p_semester" int4);
CREATE OR REPLACE FUNCTION "public"."get_subjects_for_scheduling"("p_course_id" int4=NULL::integer, "p_college_id" int4=NULL::integer, "p_cluster_id" int4=NULL::integer, "p_subject_ids" _int4=NULL::integer[], "p_year_level" int4=NULL::integer, "p_semester" int4=NULL::integer)
  RETURNS TABLE("subject_id" int4, "code" text, "description" text, "type" text, "unit" int4, "course_id" int4, "recommended_slots" int4, "cluster" int4, "min_slots" int4, "max_slots" int4, "year_level" int4, "semester" int4) AS $BODY$
BEGIN
    RETURN QUERY
    SELECT 
        s.id AS subject_id,
        s.code::TEXT,
        s.description::TEXT,
        s.type::TEXT,
        s.unit,
        s.course_id,
        -- block_id is no longer a subject property - it's selected during CP scheduling from time_blocks table
        s.recommended_slots,
        s.cluster,
        s.min_slots,
        s.max_slots,
        s.year_level,
        s.semester
    FROM subjects s
    LEFT JOIN courses c ON s.course_id = c.id
    WHERE (p_course_id IS NULL OR s.course_id = p_course_id)
      AND (p_college_id IS NULL OR c.college_id = p_college_id)
      AND (p_cluster_id IS NULL OR s.cluster = p_cluster_id)
      AND (p_subject_ids IS NULL OR s.id = ANY(p_subject_ids))
      AND (p_year_level IS NULL OR s.year_level = p_year_level)
      AND (p_semester IS NULL OR s.semester = p_semester)
    ORDER BY s.cluster, s.course_id, s.year_level, s.semester, s.code;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;

-- ----------------------------
-- Function structure for get_timeslots_by_day
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."get_timeslots_by_day"("p_day_id" int4);
CREATE OR REPLACE FUNCTION "public"."get_timeslots_by_day"("p_day_id" int4)
  RETURNS TABLE("timeslot_id" int4, "label" text, "day" int4, "start_min" int4, "end_min" int4) AS $BODY$
BEGIN
    RETURN QUERY
    SELECT 
        t.id AS timeslot_id,
        t.label::TEXT,
        t.day,
        t.start_min,
        t.end_min
    FROM timeslots t
    WHERE t.day = p_day_id
    ORDER BY t.start_min;
END;
$BODY$
  LANGUAGE plpgsql VOLATILE
  COST 100
  ROWS 1000;

-- ----------------------------
-- View structure for schedule_details
-- ----------------------------
DROP VIEW IF EXISTS "public"."schedule_details";
CREATE VIEW "public"."schedule_details" AS  SELECT s.id AS schedule_id,
    s.course_id,
    c.code AS course_code,
    c.description AS course_description,
    s.subject_id,
    subj.code AS subject_code,
    subj.description AS subject_description,
    subj.type AS subject_type,
    subj.unit AS subject_unit,
    s.instructor_id,
    (((COALESCE(i.first_name, ''::character varying)::text || ' '::text) || COALESCE(i.middle_name, ''::character varying)::text) ||
        CASE
            WHEN i.middle_name IS NULL OR i.middle_name::text = ''::text THEN ''::text
            ELSE ' '::text
        END) || COALESCE(i.last_name, ''::character varying)::text AS instructor_name,
    s.room_id,
    r.name AS room_name,
    r.type AS room_type,
    s.day_id,
    d.label AS day_label,
    s."time" AS time_label,
    s.year,
    s.semester,
    s.block
   FROM schedules s
     LEFT JOIN courses c ON c.id = s.course_id
     LEFT JOIN subjects subj ON subj.id = s.subject_id
     LEFT JOIN instructors i ON i.id = s.instructor_id
     LEFT JOIN rooms r ON r.id = s.room_id
     LEFT JOIN days d ON d.id = s.day_id;

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."building_distances_id_seq"
OWNED BY "public"."building_distances"."id";
SELECT setval('"public"."building_distances_id_seq"', 11, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."buildings_id_seq"
OWNED BY "public"."buildings"."id";
SELECT setval('"public"."buildings_id_seq"', 10, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."candidates_id_seq"
OWNED BY "public"."candidates"."id";
SELECT setval('"public"."candidates_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."colleges_id_seq"
OWNED BY "public"."colleges"."id";
SELECT setval('"public"."colleges_id_seq"', 11, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."courses_id_seq"
OWNED BY "public"."courses"."id";
SELECT setval('"public"."courses_id_seq"', 10, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."curriculum_subjects_id_seq"
OWNED BY "public"."curriculum_subjects"."id";
SELECT setval('"public"."curriculum_subjects_id_seq"', 144, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."days_id_seq"
OWNED BY "public"."days"."id";
SELECT setval('"public"."days_id_seq"', 8, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."instructors_id_seq"
OWNED BY "public"."instructors"."id";
SELECT setval('"public"."instructors_id_seq"', 39, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."rooms_id_seq"
OWNED BY "public"."rooms"."id";
SELECT setval('"public"."rooms_id_seq"', 32, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."schedules_id_seq"
OWNED BY "public"."schedules"."id";
SELECT setval('"public"."schedules_id_seq"', 12728, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."subjects_id_seq"
OWNED BY "public"."subjects"."id";
SELECT setval('"public"."subjects_id_seq"', 227, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."swap_requests_id_seq"
OWNED BY "public"."swap_requests"."id";
SELECT setval('"public"."swap_requests_id_seq"', 7, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."timeslots_id_seq"
OWNED BY "public"."timeslots"."id";
SELECT setval('"public"."timeslots_id_seq"', 95, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."users_id_seq"
OWNED BY "public"."users"."id";
SELECT setval('"public"."users_id_seq"', 41, true);

-- ----------------------------
-- Indexes structure for table building_distances
-- ----------------------------
CREATE INDEX "ix_building_distances_id" ON "public"."building_distances" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table building_distances
-- ----------------------------
ALTER TABLE "public"."building_distances" ADD CONSTRAINT "uq_building_distance_pair" UNIQUE ("from_building_id", "to_building_id");

-- ----------------------------
-- Primary Key structure for table building_distances
-- ----------------------------
ALTER TABLE "public"."building_distances" ADD CONSTRAINT "building_distances_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table buildings
-- ----------------------------
CREATE INDEX "ix_buildings_id" ON "public"."buildings" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table buildings
-- ----------------------------
ALTER TABLE "public"."buildings" ADD CONSTRAINT "buildings_name_key" UNIQUE ("name");

-- ----------------------------
-- Primary Key structure for table buildings
-- ----------------------------
ALTER TABLE "public"."buildings" ADD CONSTRAINT "buildings_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table candidates
-- ----------------------------
CREATE INDEX "idx_candidates_course_id" ON "public"."candidates" USING btree (
  "course_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_candidates_course_sem_year" ON "public"."candidates" USING btree (
  "course_id" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "semester" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "year" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_candidates_room_id" ON "public"."candidates" USING btree (
  "room_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_candidates_semester" ON "public"."candidates" USING btree (
  "semester" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_candidates_timeslot_id" ON "public"."candidates" USING btree (
  "timeslot_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_candidates_year" ON "public"."candidates" USING btree (
  "year" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table candidates
-- ----------------------------
ALTER TABLE "public"."candidates" ADD CONSTRAINT "candidates_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table colleges
-- ----------------------------
CREATE INDEX "ix_colleges_id" ON "public"."colleges" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table colleges
-- ----------------------------
ALTER TABLE "public"."colleges" ADD CONSTRAINT "colleges_code_key" UNIQUE ("code");

-- ----------------------------
-- Primary Key structure for table colleges
-- ----------------------------
ALTER TABLE "public"."colleges" ADD CONSTRAINT "colleges_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table courses
-- ----------------------------
CREATE INDEX "idx_courses_code" ON "public"."courses" USING btree (
  "code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_courses_college_id" ON "public"."courses" USING btree (
  "college_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table courses
-- ----------------------------
ALTER TABLE "public"."courses" ADD CONSTRAINT "courses_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table curriculum_subjects
-- ----------------------------
CREATE INDEX "ix_curriculum_subjects_id" ON "public"."curriculum_subjects" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table curriculum_subjects
-- ----------------------------
ALTER TABLE "public"."curriculum_subjects" ADD CONSTRAINT "curriculum_subjects_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Uniques structure for table days
-- ----------------------------
ALTER TABLE "public"."days" ADD CONSTRAINT "days_label_key" UNIQUE ("label");

-- ----------------------------
-- Primary Key structure for table days
-- ----------------------------
ALTER TABLE "public"."days" ADD CONSTRAINT "days_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table instructors
-- ----------------------------
CREATE INDEX "idx_instructors_college_id" ON "public"."instructors" USING btree (
  "college_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_instructors_username" ON "public"."instructors" USING btree (
  "username" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table instructors
-- ----------------------------
ALTER TABLE "public"."instructors" ADD CONSTRAINT "instructors_username_key" UNIQUE ("username");

-- ----------------------------
-- Primary Key structure for table instructors
-- ----------------------------
ALTER TABLE "public"."instructors" ADD CONSTRAINT "instructors_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table rooms
-- ----------------------------
CREATE INDEX "idx_rooms_capacity" ON "public"."rooms" USING btree (
  "capacity" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_rooms_cluster" ON "public"."rooms" USING btree (
  "cluster" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_rooms_type" ON "public"."rooms" USING btree (
  "type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_rooms_type_capacity" ON "public"."rooms" USING btree (
  "type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "capacity" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Checks structure for table rooms
-- ----------------------------
ALTER TABLE "public"."rooms" ADD CONSTRAINT "check_room_type" CHECK (type::text = ANY (ARRAY['LEC'::character varying::text, 'LAB'::character varying::text]));

-- ----------------------------
-- Primary Key structure for table rooms
-- ----------------------------
ALTER TABLE "public"."rooms" ADD CONSTRAINT "rooms_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table schedules
-- ----------------------------
CREATE INDEX "idx_schedules_course_id" ON "public"."schedules" USING btree (
  "course_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_course_semester" ON "public"."schedules" USING btree (
  "course_id" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "semester" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_course_year_sem" ON "public"."schedules" USING btree (
  "course_id" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "year" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "semester" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_day_id" ON "public"."schedules" USING btree (
  "day_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_day_time" ON "public"."schedules" USING btree (
  "day_id" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "time" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_instructor_day_time" ON "public"."schedules" USING btree (
  "instructor_id" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "day_id" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "time" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_instructor_id" ON "public"."schedules" USING btree (
  "instructor_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_room_day_time" ON "public"."schedules" USING btree (
  "room_id" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "day_id" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "time" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_room_id" ON "public"."schedules" USING btree (
  "room_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_sem_day_time" ON "public"."schedules" USING btree (
  "semester" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "day_id" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "time" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_semester" ON "public"."schedules" USING btree (
  "semester" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_semester_year" ON "public"."schedules" USING btree (
  "semester" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "year" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_subject_id" ON "public"."schedules" USING btree (
  "subject_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_time" ON "public"."schedules" USING btree (
  "time" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_schedules_year" ON "public"."schedules" USING btree (
  "year" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table schedules
-- ----------------------------
ALTER TABLE "public"."schedules" ADD CONSTRAINT "uq_room_time_block_course" UNIQUE ("room_id", "day_id", "time", "year", "semester", "block", "course_id");
ALTER TABLE "public"."schedules" ADD CONSTRAINT "uq_instructor_time_block_course" UNIQUE ("instructor_id", "day_id", "time", "year", "semester", "block", "course_id");

-- ----------------------------
-- Primary Key structure for table schedules
-- ----------------------------
ALTER TABLE "public"."schedules" ADD CONSTRAINT "schedules_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table subjects
-- ----------------------------
CREATE INDEX "idx_subjects_cluster" ON "public"."subjects" USING btree (
  "cluster" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_subjects_cluster_year_sem" ON "public"."subjects" USING btree (
  "cluster" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "year_level" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "semester" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_subjects_code" ON "public"."subjects" USING btree (
  "code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_subjects_course_cluster" ON "public"."subjects" USING btree (
  "course_id" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "cluster" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_subjects_course_id" ON "public"."subjects" USING btree (
  "course_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_subjects_course_year_sem" ON "public"."subjects" USING btree (
  "course_id" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "year_level" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "semester" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_subjects_semester" ON "public"."subjects" USING btree (
  "semester" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_subjects_type" ON "public"."subjects" USING btree (
  "type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_subjects_year_level" ON "public"."subjects" USING btree (
  "year_level" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Checks structure for table subjects
-- ----------------------------
ALTER TABLE "public"."subjects" ADD CONSTRAINT "check_subject_type" CHECK (type::text = ANY (ARRAY['LEC'::character varying::text, 'LAB'::character varying::text]));

-- ----------------------------
-- Primary Key structure for table subjects
-- ----------------------------
ALTER TABLE "public"."subjects" ADD CONSTRAINT "subjects_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table swap_requests
-- ----------------------------
CREATE INDEX "idx_swap_requests_requester" ON "public"."swap_requests" USING btree (
  "requester_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_swap_requests_status" ON "public"."swap_requests" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_swap_requests_target" ON "public"."swap_requests" USING btree (
  "target_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "ix_swap_requests_id" ON "public"."swap_requests" USING btree (
  "id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Checks structure for table swap_requests
-- ----------------------------
ALTER TABLE "public"."swap_requests" ADD CONSTRAINT "check_swap_status" CHECK (status::text = ANY (ARRAY['pending'::character varying, 'accepted'::character varying, 'rejected'::character varying]::text[]));

-- ----------------------------
-- Primary Key structure for table swap_requests
-- ----------------------------
ALTER TABLE "public"."swap_requests" ADD CONSTRAINT "swap_requests_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table time_blocks
-- ----------------------------
ALTER TABLE "public"."time_blocks" ADD CONSTRAINT "time_blocks_pkey" PRIMARY KEY ("block_id");

-- ----------------------------
-- Indexes structure for table timeslots
-- ----------------------------
CREATE INDEX "idx_timeslots_day" ON "public"."timeslots" USING btree (
  "day" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_timeslots_day_start" ON "public"."timeslots" USING btree (
  "day" "pg_catalog"."int4_ops" ASC NULLS LAST,
  "start_min" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_timeslots_end_min" ON "public"."timeslots" USING btree (
  "end_min" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_timeslots_start_min" ON "public"."timeslots" USING btree (
  "start_min" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table timeslots
-- ----------------------------
ALTER TABLE "public"."timeslots" ADD CONSTRAINT "timeslots_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table users
-- ----------------------------
CREATE INDEX "idx_users_instructor_id" ON "public"."users" USING btree (
  "instructor_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_users_role" ON "public"."users" USING btree (
  "role" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE UNIQUE INDEX "ix_users_username" ON "public"."users" USING btree (
  "username" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Checks structure for table users
-- ----------------------------
ALTER TABLE "public"."users" ADD CONSTRAINT "check_role" CHECK (role::text = ANY (ARRAY['admin'::character varying::text, 'registrar'::character varying::text, 'instructor'::character varying::text]));

-- ----------------------------
-- Primary Key structure for table users
-- ----------------------------
ALTER TABLE "public"."users" ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Foreign Keys structure for table building_distances
-- ----------------------------
ALTER TABLE "public"."building_distances" ADD CONSTRAINT "building_distances_from_building_id_fkey" FOREIGN KEY ("from_building_id") REFERENCES "public"."buildings" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."building_distances" ADD CONSTRAINT "building_distances_to_building_id_fkey" FOREIGN KEY ("to_building_id") REFERENCES "public"."buildings" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table buildings
-- ----------------------------
ALTER TABLE "public"."buildings" ADD CONSTRAINT "buildings_college_id_fkey" FOREIGN KEY ("college_id") REFERENCES "public"."colleges" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table candidates
-- ----------------------------
ALTER TABLE "public"."candidates" ADD CONSTRAINT "candidates_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "public"."courses" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."candidates" ADD CONSTRAINT "candidates_room_id_fkey" FOREIGN KEY ("room_id") REFERENCES "public"."rooms" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."candidates" ADD CONSTRAINT "candidates_timeslot_id_fkey" FOREIGN KEY ("timeslot_id") REFERENCES "public"."timeslots" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table courses
-- ----------------------------
ALTER TABLE "public"."courses" ADD CONSTRAINT "courses_college_id_fkey" FOREIGN KEY ("college_id") REFERENCES "public"."colleges" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table curriculum_subjects
-- ----------------------------
ALTER TABLE "public"."curriculum_subjects" ADD CONSTRAINT "curriculum_subjects_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "public"."courses" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table instructors
-- ----------------------------
ALTER TABLE "public"."instructors" ADD CONSTRAINT "instructors_college_id_fkey" FOREIGN KEY ("college_id") REFERENCES "public"."colleges" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table rooms
-- ----------------------------
ALTER TABLE "public"."rooms" ADD CONSTRAINT "rooms_building_id_fkey" FOREIGN KEY ("building_id") REFERENCES "public"."buildings" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."rooms" ADD CONSTRAINT "rooms_college_id_fkey" FOREIGN KEY ("college_id") REFERENCES "public"."colleges" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table schedules
-- ----------------------------
ALTER TABLE "public"."schedules" ADD CONSTRAINT "schedules_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "public"."courses" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."schedules" ADD CONSTRAINT "schedules_day_id_fkey" FOREIGN KEY ("day_id") REFERENCES "public"."days" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."schedules" ADD CONSTRAINT "schedules_instructor_id_fkey" FOREIGN KEY ("instructor_id") REFERENCES "public"."instructors" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."schedules" ADD CONSTRAINT "schedules_room_id_fkey" FOREIGN KEY ("room_id") REFERENCES "public"."rooms" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."schedules" ADD CONSTRAINT "schedules_subject_id_fkey" FOREIGN KEY ("subject_id") REFERENCES "public"."subjects" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table subjects
-- ----------------------------
ALTER TABLE "public"."subjects" ADD CONSTRAINT "subjects_course_id_fkey" FOREIGN KEY ("course_id") REFERENCES "public"."courses" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table swap_requests
-- ----------------------------
ALTER TABLE "public"."swap_requests" ADD CONSTRAINT "swap_requests_requester_id_fkey" FOREIGN KEY ("requester_id") REFERENCES "public"."instructors" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."swap_requests" ADD CONSTRAINT "swap_requests_requester_schedule_id_fkey" FOREIGN KEY ("requester_schedule_id") REFERENCES "public"."schedules" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."swap_requests" ADD CONSTRAINT "swap_requests_target_id_fkey" FOREIGN KEY ("target_id") REFERENCES "public"."instructors" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
ALTER TABLE "public"."swap_requests" ADD CONSTRAINT "swap_requests_target_schedule_id_fkey" FOREIGN KEY ("target_schedule_id") REFERENCES "public"."schedules" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table time_blocks
-- ----------------------------
ALTER TABLE "public"."time_blocks" ADD CONSTRAINT "time_blocks_day_id_fkey" FOREIGN KEY ("day_id") REFERENCES "public"."days" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;

-- ----------------------------
-- Foreign Keys structure for table users
-- ----------------------------
ALTER TABLE "public"."users" ADD CONSTRAINT "users_instructor_id_fkey" FOREIGN KEY ("instructor_id") REFERENCES "public"."instructors" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION;
