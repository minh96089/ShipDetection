CREATE DATABASE shipdb;
GO
USE shipdb;
GO

CREATE TABLE users (
    user_id INT IDENTITY(1,1) PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    full_name NVARCHAR(100),
    role VARCHAR(20) DEFAULT 'user',
    created_at DATETIME DEFAULT GETDATE()
);
GO

INSERT INTO users (username, password, full_name, role)  
VALUES ('admin', '1', 'Administrator', 'admin');
GO

CREATE TABLE ship (
    ship_id INT IDENTITY(1,1) PRIMARY KEY,
    so_hieu VARCHAR(50) NOT NULL UNIQUE,
    loai_tau NVARCHAR(100),
    thoi_gian_tao DATETIME DEFAULT GETDATE(),
    mo_ta NVARCHAR(500),
    anh_dai_dien NVARCHAR(500)
);
GO

CREATE UNIQUE INDEX IX_Ship_SoHieu_Unique ON ship(so_hieu);
GO

CREATE TABLE shiplog (
    unique_id VARCHAR(100) PRIMARY KEY,
    track_id INT NOT NULL,
    loai_tau NVARCHAR(100) NOT NULL,
    gio_phat_hien DATETIME NOT NULL,
    hinh_anh NVARCHAR(500),
    nguon NVARCHAR(500),
    ghi_chu NVARCHAR(500),
    so_hieu VARCHAR(50),
    do_tin_cay_ocr FLOAT,
    CONSTRAINT FK_ShipLog_Ship FOREIGN KEY (so_hieu) 
    REFERENCES ship(so_hieu)
    ON DELETE SET NULL 
    ON UPDATE CASCADE
);
GO

CREATE TABLE ship_trajectory (
    traj_id        INT IDENTITY(1,1) PRIMARY KEY,
    unique_id      VARCHAR(100) NOT NULL,
    session_id     VARCHAR(150) NOT NULL,
    track_id       INT NOT NULL,
    frame_index    INT NOT NULL,
    center_x       INT NOT NULL,
    center_y       INT NOT NULL,
    bbox_x1        INT,
    bbox_y1        INT,
    bbox_x2        INT,
    bbox_y2        INT,
    confidence     FLOAT,
    thoi_gian      DATETIME DEFAULT GETDATE(),
    CONSTRAINT FK_Traj_ShipLog FOREIGN KEY (unique_id)
        REFERENCES shiplog(unique_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);
GO

CREATE INDEX IX_Traj_UniqueId     ON ship_trajectory (unique_id);
CREATE INDEX IX_Traj_SessionTrack ON ship_trajectory (session_id, track_id);
GO

CREATE TABLE alerts (
    alert_id INT IDENTITY(1,1) PRIMARY KEY,
    unique_id VARCHAR(100) NOT NULL,
    track_id INT NOT NULL,
    session_id VARCHAR(150) NOT NULL,
    alert_type NVARCHAR(100) DEFAULT 'Xâm nhập vùng cấm',
    alert_time DATETIME DEFAULT GETDATE(),
    center_x INT,
    center_y INT,
    loai_tau NVARCHAR(100),
    so_hieu VARCHAR(50),
    do_tin_cay_ocr FLOAT,
    telegram_sent BIT DEFAULT 0,
    hinh_anh NVARCHAR(500),
    ghi_chu NVARCHAR(500),
    status VARCHAR(20) DEFAULT 'new',
    handled_by INT,
    handled_at DATETIME,
    note NVARCHAR(500),
    CONSTRAINT FK_Alerts_ShipLog FOREIGN KEY (unique_id)
        REFERENCES shiplog(unique_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    CONSTRAINT FK_Alerts_User FOREIGN KEY (handled_by)
        REFERENCES users(user_id)
        ON DELETE SET NULL
);
GO

CREATE INDEX IX_Alerts_SessionId ON alerts (session_id);
CREATE INDEX IX_Alerts_TrackId ON alerts (track_id);
CREATE INDEX IX_Alerts_Time ON alerts (alert_time);
GO
