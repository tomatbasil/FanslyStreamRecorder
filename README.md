# Fansly Stream Recorder

An automated tool to record, compress and upload live streams from Fansly creators.

## Requirements

-   Python
-   FFmpeg installed and available in system PATH

## Installation

### Install ffmpeg

#### Windows:

1. Download FFmpeg from the [official website](https://ffmpeg.org/download.html#build-windows) or use a Windows build like [gyan.dev](https://www.gyan.dev/ffmpeg/builds/)
2. Extract the archive to a location like `C:\ffmpeg`
3. Add FFmpeg to your PATH:
    - Right-click on 'This PC' or 'My Computer' and select 'Properties'
    - Click 'Advanced system settings'
    - Click 'Environment Variables'
    - Under 'System variables', find and select 'Path', then click 'Edit'
    - Click 'New' and add the path to FFmpeg's bin folder (e.g., `C:\ffmpeg\bin`)
    - Click 'OK' on all dialogs

#### macOS:

```bash
brew install ffmpeg
```

#### Linux:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install ffmpeg

# CentOS/RHEL
sudo yum install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg
```

### Install Fansly Stream Recorder

1. Clone this repository:

```bash
git clone https://github.com/tomatbasil/FanslyStreamRecorder
cd FanslyStreamRecorder
```

2. Install required Python packages:

```bash
pip install -r requirements.txt
```

3. Create `.env` and add your Fansly authentication token, Discord bot token (optional) and Bunkr token (optional):

To get your fansly auth token, you can run this in the console: `this.getAuth()`

```env
FANSLY_AUTH_TOKEN=your_token_here
DISCORD_BOT_TOKEN=your_discord_bot_token_here
BUNKR_TOKEN=your_token_here
```

4. Stream/ Thumbnail uploading

Gofile video uploads work without any configuration.

To upload to bunkr, you will need to add a `BUNKR_TOKEN` to the `.env` file. You can find it on the bunkr dashboard if you look at your localstorage, alternatively paste this into to console: `console.log(localStorage.getItem("token"))`

If you want to use jpg5 for uploading thumbnails, create a file named `jpg5_cookies.json` in the root folder. Use something like [Cookie-Editor](https://github.com/Moustachauve/cookie-editor) to get the cookies as a json file.

## Usage

Run the script:

```bash
python main.py
```

## Settings

All configuration options are stored in `config.yaml` in the project root directory. On first run, you'll be guided through an interactive setup process to create this file.

### Available Settings

#### General Settings

| Setting            | Description                                                              | Default Value     | Type            |
| ------------------ | ------------------------------------------------------------------------ | ----------------- | --------------- |
| `output_directory` | Directory where recordings will be saved                                 | `recordings/`     | Path            |
| `users_to_monitor` | List of Fansly usernames to monitor                                      | `[]` (empty list) | List of strings |
| `protected_users`  | List of Fansly usernames who's videos should never be removed by cleanup | `[]` (empty list) | List of strings |
| `check_interval`   | Interval in seconds to check for live streams                            | `60`              | Integer         |

#### Video Settings

| Setting                           | Description                                  | Default Value | Type    |
| --------------------------------- | -------------------------------------------- | ------------- | ------- |
| `generate_thumbnail`              | Generate a thumbnail for recorded videos     | `True`        | Boolean |
| `compress_videos`                 | Compress videos after recording              | `True`        | Boolean |
| `delete_original`                 | Delete original video file after compression | `True`        | Boolean |
| `upload_videos`                   | Upload videos after recording                | `False`       | Boolean |
| `delete_split_video_after_upload` | Delete split video files after upload        | `True`        | Boolean |

#### Disk Cleanup Settings

| Setting                 | Description                                 | Default Value | Type    |
| ----------------------- | ------------------------------------------- | ------------- | ------- |
| `remove_old_recordings` | Remove old recordings to free up disk space | `True`        | Boolean |
| `min_free_disk_space`   | Minimum free disk space to maintain in GB   | `20.0`        | Float   |

#### Discord Notification Settings

| Setting              | Description                          | Default Value       | Type    |
| -------------------- | ------------------------------------ | ------------------- | ------- |
| `discord_enable`     | Enable Discord notifications         | `False`             | Boolean |
| `discord_channel_id` | Discord channel ID for notifications | `""` (empty string) | String  |

### Example Configuration

Below is an example of a complete `config.yaml` file:

```yaml
output_directory: recordings
users_to_monitor:
    - username1
    - username2
check_interval: 60
generate_thumbnail: true
compress_videos: true
delete_original: true
upload_videos: false
delete_split_video_after_upload: true
remove_old_recordings: true
min_free_disk_space: 20.0
discord_enable: false
discord_channel_id: ""
```

You can manually edit this file with any text editor or delete it to restart the configuration wizard on next run.
