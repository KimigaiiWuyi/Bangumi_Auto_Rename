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

>  ⚠提示：无论使用下面哪种方式，都必须携带参数，参数需要自己调整
>
> [命令行怎么写？](#命令行怎么写（参数详解）)

### 零、申请你的TMDB_API_KEY

- 进入[官网](https://www.themoviedb.org/settings/api)申请
- 复制你的**API 密钥**，后续会用到

### 一、下载EXE文件

- 无需Python环境，开箱即用
- 下载[Release](https://github.com/KimigaiiWuyi/Bangumi_Auto_Rename/releases)中预先上传的`.exe`文件，即可开始使用

### 二、使用

- 打开终端（Win+R输入**cmd.exe**，回车，或者右键菜单可以打开）
- 输入**命令**，命令构造方式如下：
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

- 需要关注的参数有几个
  - `--w`：这个参数可以填`TASK`或者`ALL`，`ALL`模式对应批量整理，适用于一个输入目录下存在多个剧集的情况，`TASK`适合QBIT下载完成之后自动任务，可以识别单个剧集，包括剧集中同时存在剧场版&不同季度动画子文件夹得情况
  - `--i`：输入目录
  - `--k` ：这个是需要自己去[申请](https://www.themoviedb.org/settings/api)的，申请完之后可以替换下面示例中的key
  - `--t` ：这个参数如果填入`no`或者`real`等就会把识别到的剧集和电影放入`o_bangumi `目录和`o_movie`目录，如果是不填或者填入`Anime`就会把识别到的剧集放入`o_anime`和`o_anime_movie`目录
- 这里给出几个示例，方便复制
  - 下面这个命令是
  - `--t`为`Anime`代表类型为动漫类型，只会输出到`o_anime`和`o_anime_movie`路径下
  - 程序路径: `"F:\网盘\Bangumi_Auto_Rename.exe"`
  - 输入/处理路径为`"D:\Download\Anime\[mawen1250&VCB-Studio] Toradora! [Hi10p_1080p]"`
  - 动漫剧集输出路径：`"D:\TEST\OUTPUT\anime"``
  - 电影输出路径：`"D:\TEST\OUTPUT\movie"`
  - 动漫电影输出路径：`"D:\TEST\OUTPUT\anime_movie"`
  - 真人剧集输出路径：`"D:\TEST\OUTPUT\bangumi"`
- 直接复制后修改即可：

```shell
"F:\网盘\Bangumi_Auto_Rename.exe" --w "TASK" --p "LINK" --i "D:\Download\Anime\[mawen1250&VCB-Studio] Toradora! [Hi10p_1080p]" --t "Anime" --k "e0f999999ea2d4f1cc99993762417df" --o_anime "D:\TEST\OUTPUT\anime" --o_movie "D:\TEST\OUTPUT\movie" --o_anime_movie "D:\TEST\OUTPUT\anime_movie" --o_bangumi "D:\TEST\OUTPUT\bangumi"
```

### 三、在qBittorrent下载完成后自动调用该程序

> ⚠注意：箭头处的命令需要根据上面命令行自己写一下，照抄无效！（下面有提供示例）

- 打开软件，**工具** -> **设置** -> 弹出窗口中找到**下载** -> 往下滚动 -> **Torrent完成时运行**
- 根据自己的配置，写入命令，**应用**保存即可

![qbit.png](https://s2.loli.net/2024/06/26/GXCfjaNKQSmZxDs.png)

- 这里的命令相比于上面的命令行，需要做一些小的调整，首先一点是`--i`的输入，**一定**要用`"%F"`替换（上图可能是`%D`，那是错误的，不要关心图上的命令），这样就是每次种子实际下载的路径了
- 一个是`--t`的输入，**可以**用`"$G"`替换，代表着创建种子时候的标签，这里如果下载的是动漫剧集，可以不用输入标签，如果是真人剧集，可以带上`no`的标签，自动整理
- 填入示例如下，复制的话需要自己修改一下四个**保存路径**和**程序路径**和TMDB的**Key**。

```shell
"F:\网盘\Bangumi_Auto_Rename.exe" --w "TASK" --p "LINK" --i "%F" --t "%G" --k "e0fde99999999999773762417df" --o_anime "D:\Anime" --o_movie "D:\Moive" --o_anime_movie "E:\AnimeMoive" --o_bangumi "E:\Bangumi"
```

## 需要注意的

- 该程序依靠**TMDB API**（因为Emby也是一样的，可以保证精准度），因此对**网络环境**有一定要求！
- 该程序更加适用于动画剧集的重命名，对于电影、剧集，本身Emby的刮削足够精准了。
- 识别率并不是100%，如果有识别错误的，带上截图，提Issuse！
- 该程序使用情况覆盖了很多，但是像是非常复杂的情况，例如**物语系列**这种重量级剧集（加上TMDB对于物语系列的剧集分类，非常的复杂），请不要使用本程序
- 如果已经使用了本程序刮削错误的情况，因为默认是**硬链接**模式，所以直接删除目标文件夹的对应文件即可，不会影响到源文件！
- 有任何使用上的问题或者建议都可以提issuse，尽力解答！

- 如果本插件对你有帮助，不要忘了点个Star~
- 本项目仅供学习使用，请勿用于商业用途
- [爱发电](https://afdian.com/a/KimigaiiWuyi)
- [GPL-3.0 License](https://github.com/KimigaiiWuyi/Bangumi_Auto_Rename/blob/main/LICENSE) ©[@KimigaiiWuyi](https://github.com/KimigaiiWuyi)
