// 获取当前时间的函数
function getCurrentTime() {
  const now = new Date();
  const hours = now.getHours().toString().padStart(2, '0');
  const minutes = now.getMinutes().toString().padStart(2, '0');
  const seconds = now.getSeconds().toString().padStart(2, '0');
  return `${hours}:${minutes}:${seconds}`;
}

// 打印带有时间戳的日志
function log(...args) {
  const timestamp = getCurrentTime();
  console.log(`[${timestamp}]`, ...args);
}

document.addEventListener('DOMContentLoaded', function () {
  var socket = io.connect('http://' + '127.0.0.1' + ':' + '8000');

  socket.on('connect', function () {
    console.log('WebSocket connected!');
    socket.emit('start_data_transfer');  // 告知服务器开始数据传输
  });

  socket.on('progress', function (data) {
    log('Progress: ' + JSON.stringify(data));

    if (data.progress)
      document.getElementById('progressBar').style.width = data.progress + '%';

    if (data.status)
      document.getElementById('progress-status').textContent = data.status;

    // 当进度完成时,隐藏进度条
    if (data.progress >= 100) {
      document.getElementById('progress-container-wrapper').style.display = 'none';
      document.getElementById('progress-status').style.display = 'none';
    }
  });

  socket.on('data', function (data) {
    if (!data.data) return

    document.getElementById('table-container').style.display = 'block';
    createTable(data.data, data.page)
  });

  function createTable(data, page) {
    var container = document.getElementById('table-container');

    // 创建一个新的表格
    var table = document.createElement('table');
    table.classList.add('data-table'); // 添加样式类

    // 遍历 JSON 对象
    for (var key in data) {
      if (data.hasOwnProperty(key)) {
        var value = data[key];

        // 创建表格行
        var row = table.insertRow(-1);
        var cellKey = row.insertCell(0);
        var cellValue = row.insertCell(1);
        cellKey.innerHTML = key;
        cellValue.innerHTML = value;
      }
    }

    // 创建表格标题
    const title = document.createElement('h3');
    title.textContent = `第 ${page} 页`;
    container.appendChild(title);

    // 将表格添加到容器
    container.appendChild(table);
  }

  function upload_file(elem) {
    // 检查是否选择了文件
    if (elem.files.length <= 0)
      return

    var file = elem.files[0];
    var formData = new FormData();
    formData.append('file', file);
    log("11 ", file)

    var xhr = new XMLHttpRequest();
    xhr.open('POST', '/upload', true);
    xhr.onload = function () {
      if (xhr.status === 200) {
        console.log(xhr.responseText)

        var response = JSON.parse(xhr.responseText);
        var uploadedFileName = response.filename;
        log('文件上传成功', uploadedFileName);

        table = document.getElementById("table-container");  
        table.innerHTML = ""
        document.getElementById('progress-container-wrapper').style.display = 'block';
        document.getElementById('progress-status').style.display = 'block';
          
        // 更新 embed 标签的 src 属性
        var pdfViewer = document.getElementById('pdf-viewer');
        var embedTag = '<embed src="/uploads/' + uploadedFileName + '" type="application/pdf" width="100%" height="100%" />';
        pdfViewer.innerHTML = embedTag;

        document.getElementById('second-upload-btn').style.display = 'block';
        document.getElementById('json-viewer').style.display = 'block';

      } else {
        log('文件上传失败');
      }
    };

    xhr.send(formData);
  }

  document.getElementById('file-upload').addEventListener('change', function () {
    upload_file(this)
  });
  document.getElementById('second-file-upload').addEventListener('change', function () {
    upload_file(this)
  });

  var isDragging = false;
  var leftPanel = document.getElementById('pdf-viewer');
  var rightPanel = document.getElementById('json-viewer');
  var gutter = document.getElementById('gutter');
  var container = document.getElementById('container');

  gutter.addEventListener('mousedown', function (e) {
    e.preventDefault();
    isDragging = true;
  });

  document.addEventListener('mousemove', function (e) {
    // Only resize if dragging is active
    if (!isDragging) return;

    var containerRect = container.getBoundingClientRect();
    var leftWidth = e.clientX - containerRect.left;
    var rightWidth = containerRect.right - e.clientX;

    leftPanel.style.width = `${leftWidth}px`;
    //    rightPanel.style.flexGrow = 0; // 防止右侧面板伸展
  });

  document.addEventListener('mouseup', function (e) {
    isDragging = false;
  });

  document.getElementById('upload-btn').addEventListener('click', function () {
    document.getElementById('file-upload').click();
  });
  
  document.getElementById('second-upload-btn').addEventListener('click', function () {
    document.getElementById('second-file-upload').click();
  });
});
