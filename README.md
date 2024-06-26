## 简介

😣受不了动漫剧集的命名与Emby自动刮削格式不兼容？

🥰本项目可以将**大部分**下载的剧集（包括动漫、电影、番剧等）转为Emby所需要的**文件结构**！

🚀支持剪切、复制、**硬链接（默认）**三种**移动/重命名**方式！

✨并且你可以通过简单的配置，让qBittorrent每次下载结束之后**自动执行转换！**

🥳支持复杂的目录结构！以VCB-Studio的**Re:从零开始的异世界生活**剧集合集为例：

```shell
├─[VCB-Studio] Re Zero kara Hajimeru Isekai Seikatsu
│  ├─[VCB-Studio] Re Zero kara Hajimeru Isekai Seikatsu 2nd Season [Ma10p_1080p]
│  ├─[VCB-Studio] Re Zero kara Hajimeru Isekai Seikatsu Hyouketsu no Kizuna [Ma10p_1080p]
│  ├─[VCB-Studio] Re Zero kara Hajimeru Isekai Seikatsu Memory Snow [Ma10p_1080p]
│  ├─[VCB-Studio] Re Zero kara Hajimeru Isekai Seikatsu [Ma10p_1080p]
```

可以看到大的集合里面同时包括以下**子文件夹**内容：第一季、第二季、电影冰结之绊、电影雪之回忆，而你只需要运行该程序，即可自动分门别类，**电影/番剧**会被格式化后**分别的**、正确的**复制/硬链接**到**你指定的文件夹**！

## 使用效果

![1.png](https://s2.loli.net/2024/06/26/oe8jrEg7wqdtGZ1.png)

![2.png](https://s2.loli.net/2024/06/26/8PmycWaSe3f6htC.png)

## 使用方法（待定）

>  ⚠提示：无论使用下面哪种方式，都必须携带参数，参数需要自己调整
>
> [命令行怎么写？](#命令行怎么写（参数详解）)

### 一、调用EXE文件

- 无需Python环境，开箱即用
- 下载[Release](https://github.com/KimigaiiWuyi/Bangumi_Auto_Rename/releases)中预先上传的`.exe`文件，即可开始使用
- 打开命令行，输入命令

```shell
$ "下载的文件路径\Bangumi_Auto_Rename.exe"
```

### 二、命令行直接使用

- 需要Python环境、安装依赖等等
- 打开终端，输入命令

```shell
$ python Bangumi_Auto_Rename.py
```

### 三、在qBittorrent下载完成后自动调用该程序

> ⚠注意：箭头处的命令需要根据上面命令行自己写一下，照抄无效！

- 打开软件，**工具** -> **设置** -> 弹出窗口中找到**下载** -> 往下滚动 -> **Torrent完成时运行**
- 根据自己的配置，写入命令，**应用**保存即可

![qbit.png](https://s2.loli.net/2024/06/26/GXCfjaNKQSmZxDs.png)

### 命令行怎么写（参数详解）

```shell
  -h, --help                            show this help message and exit
  --w W                                 工作模式: ALL/TASK(默认TASK即可)
  --p P                                 处理模式: MOVE/COPY/LINK(剪切、复制、硬链接)
  --t T                                 是否为动画类型
  --k K                                 TMDB_Key, 需要申请
  --i I                                 输入路径
  --o_anime O_ANIME                     动漫解析完成之后输出路径
  --o_movie O_MOVIE                     电影解析完成之后输出路径
  --o_anime_movie O_ANIME_MOVIE         动漫剧场版解析完成之后输出路径
  --o_bangumi O_BANGUMI                 剧集解析完成之后输出路径
```

### 示例

待定...
