## 更新内容

### 增加 Jellyfin 适配

可在配置页面选择服务端类型。

因为 Jellyfin 可以识别季度内 extras 文件夹，故将 extras 文件夹按季度分类。尝试增加 Jellyfin 支持的 extras 分类识别，虽然整体应该没什么效果。
此外，特别将 CD 相关文件夹链接到季度下的 others 文件夹，方便后期手动选择 theme-music 等操作。

### 优化识别能力

针对一些边界情况进行特判，且补充了一些其他情况。

### 默认开启 "all in one" 模式

传入目录时，会扫描当前目录下是否有视频文件：若无，则认为作品季度文件夹在子目录，进行递归；若有，则认为当前目录为单季度作品文件夹，正片存在于该目录下，extras 等内容存放于子文件夹。

可能增加的改动：将路径中出现的每一段名称都尝试搜索对应作品名辅助子文件夹判断（应用于系列作品）

==***注意：该改动彻底移除对单文件支持能力，且目录下不能有零碎的视频文件，不然会影响目录类型判断，并极有可能产生毁灭性的输出***==

不知是否有保留一定处理单文件的功能的需求，如传入的待处理目录下有一些单独的电影文件。~~（一部分原因也可能是是刚开始没太弄明白单文件处理逻辑然后后面也不想动了）~~



## 简介

- 😣受不了动漫剧集的命名与Emby自动刮削格式不兼容？

- 🥰本项目可以将**大部分**下载的剧集（包括动漫、电影、番剧等）转为Emby所需要的**文件结构**！

- 🚀支持剪切、复制、**硬链接（默认）**三种**移动/重命名**方式！

- ✨并且你可以通过简单的配置，让qBittorrent每次下载结束之后**自动执行转换！**

- 🥳支持复杂的目录结构！以VCB-Studio的**Re:从零开始的异世界生活**剧集合集为例：

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

## 使用方法

### 零、申请你的TMDB_API_KEY

- 进入[官网](https://www.themoviedb.org/settings/api)申请
- 复制你的**API 密钥**，后续会用到

### 一、安装 (WEB版本)

> [!IMPORTANT] 
>
> WEB版本提高了易用性、和识别准确率, 但要求必须本机内存在git和python环境！

- 确保存在Python环境（版本需要`>=3.9`）, Git环境。
- 命令行执行
  - `git clone https://github.com/KimigaiiWuyi/Bangumi_Auto_Rename.git -b web`
  - `cd Bangumi_Auto_Rename`
  - `pip install -r requirements.txt `

- 启动
  - `python -m src.start`


![.jpg](https://s2.loli.net/2025/01/13/f56LsCtKhDm1Oky.jpg)

### 二、使用

- 打开网页之后（默认端口5999，即地址为`http://127.0.0.1:5999`）
- 先点击右上角配置按钮，将刚刚的TMDB_API填入，并且配置好各个整理路径
- 点击添加任务即可使用

### 三、在qBittorrent下载完成后自动调用该程序

> ⚠注意：箭头处的命令需要根据上面命令行自己写一下，照抄无效！（下面有提供示例）

- 打开软件，**工具** -> **设置** -> 弹出窗口中找到**下载** -> 往下滚动 -> **Torrent完成时运行**
- 根据自己的配置，写入命令，**应用**保存即可

![image.png](https://s2.loli.net/2025/02/02/GfcTiNJXs4EFDWm.png)

- 这里的命令相比于上面的命令行，需要做一些小的调整，首先一点是`path=`的输入，**一定**要用`"%F"`替换（上图可能是`%D`，那是错误的，不要关心图上的命令），这样就是每次种子实际下载的路径了
- 一个是`tag=`的输入，**可以**用`"$G"`替换，代表着创建种子时候的标签，这里如果下载的是动漫剧集，需要带上`anime`的标签，如果是电影，带上`movie`的标签，方便自动整理到对应路径，如果无任何标签，是否是电影会**自动判断**，是否是动漫则**默认为否**，如果不需要处理，可以传入`no_process`的标签
- 填入示例如下

```shell
curl -d "path="%F"&tag="%G"" http://127.0.0.1:5999/sendTask -f
```

### 四、更新

- 进入文件夹内，`cd Bangumi_Auto_Rename`
- 执行`git pull`

## 需要注意的

- 该程序依靠**TMDB API**（因为Emby也是一样的，可以保证精准度），因此对**网络环境**有一定要求！
- 该程序更加适用于动画剧集的重命名，对于电影、剧集，本身Emby的刮削足够精准了。
- 识别率并不是100%，如果有识别错误的，带上截图，提Issues！
- 该程序使用情况覆盖了很多，但是像是非常复杂的情况，例如**物语系列**这种重量级剧集（加上TMDB对于物语系列的剧集分类，非常的复杂），请不要使用本程序
- 如果已经使用了本程序刮削错误的情况，因为默认是**硬链接**模式，所以直接删除目标文件夹的对应文件即可，不会影响到源文件！
- 有任何使用上的问题或者建议都可以提Issues，尽力解答！

- 如果本插件对你有帮助，不要忘了点个Star~
- 本项目仅供学习使用，请勿用于商业用途
- [爱发电](https://afdian.com/a/KimigaiiWuyi)
- [GPL-3.0 License](https://github.com/KimigaiiWuyi/Bangumi_Auto_Rename/blob/main/LICENSE) ©[@KimigaiiWuyi](https://github.com/KimigaiiWuyi)
