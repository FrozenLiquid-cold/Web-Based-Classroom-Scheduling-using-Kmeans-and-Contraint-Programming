-- Migration 022: Add system_settings table
CREATE TABLE IF NOT EXISTS system_settings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    `key` VARCHAR(100) NOT NULL UNIQUE,
    value VARCHAR(255) NOT NULL,
    description VARCHAR(500) NULL,
    INDEX idx_system_settings_key (`key`)
);

-- Seed defaults
INSERT IGNORE INTO system_settings (`key`, value, description) VALUES
('regular_base_hours', '24', 'Base weekly hour limit for regular instructors (before designation deductions)'),
('visiting_base_hours', '30', 'Weekly hour limit for visiting lecturers (no deduction applied)');
